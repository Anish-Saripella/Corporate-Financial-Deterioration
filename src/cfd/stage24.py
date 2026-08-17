"""Stage 24: certify and materialize the real Phase 2 point-in-time panel."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pandas as pd

from cfd.config import read_yaml, repository_root
from cfd.ingestion.fred import FredClient
from cfd.panel import build_point_in_time_panel, certify_panel
from cfd.settings import RuntimeSettings
from cfd.stages import stage_paths


def _load_or_download_macro() -> pd.DataFrame:
    paths = stage_paths()
    root = repository_root()
    processed = paths.processed / "phase2_macro_vintages.parquet"
    if processed.exists():
        return pd.read_parquet(processed)
    settings = RuntimeSettings()
    specifications = read_yaml(root / "configs" / "macro_series.yml")["macro_series"]
    raw_root = paths.raw_fred / "phase2"
    manifests = paths.manifests / "phase2"
    raw_root.mkdir(parents=True, exist_ok=True)
    manifests.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    with FredClient(api_key=settings.require_fred_api_key()) as client:
        for specification in specifications:
            series_id = str(specification["series_id"])
            destination = raw_root / f"{series_id}.json"
            if not destination.exists():
                vintage_required = bool(specification["vintage_required"])
                client.download_observations(
                    series_id=series_id,
                    destination=destination,
                    manifest_directory=manifests,
                    realtime_start="2012-01-01" if vintage_required else date.today().isoformat(),
                    realtime_end=date.today().isoformat(),
                    output_type=4 if vintage_required else 1,
                )
            payload = json.loads(destination.read_text(encoding="utf-8"))
            for observation in payload["observations"]:
                value = observation.get("value")
                rows.append(
                    {
                        "series_id": series_id,
                        "observation_date": observation.get("date"),
                        "realtime_start": observation.get("realtime_start"),
                        "realtime_end": observation.get("realtime_end"),
                        "value": None if value in {None, "."} else float(value),
                    }
                )
    macro = pd.DataFrame(rows)
    macro.to_parquet(processed, index=False)
    return macro


def run_stage_24() -> dict[str, Any]:
    """Apply final certification and retain selected issuers with explicit quality tiers."""

    root = repository_root()
    paths = stage_paths()
    phase2_config = read_yaml(root / "configs" / "phase2.yml")
    policy = phase2_config["universe_policy"]
    universe_path = paths.processed / "phase2_frozen_universe.parquet"
    facts_path = paths.interim / "phase2_financial_facts_raw.parquet"
    for required in [universe_path, facts_path]:
        if not required.exists():
            raise FileNotFoundError(f"Required real Phase 2 artifact is missing: {required}")
    frozen = pd.read_parquet(universe_path)
    facts = pd.read_parquet(facts_path)
    facts = facts.loc[facts["cik"].isin(set(frozen["cik"].astype(str)))].copy()
    macro = _load_or_download_macro()
    macro_config = read_yaml(root / "configs" / "macro_series.yml")["macro_series"]
    cached_panel = paths.interim / "phase2_candidate_point_in_time_panel.parquet"
    candidate_panel = pd.read_parquet(cached_panel) if cached_panel.exists() else pd.DataFrame()
    required_candidate_ciks = set(frozen["cik"].astype(str))
    if candidate_panel.empty or not required_candidate_ciks.issubset(
        set(candidate_panel["cik"].astype(str))
    ):
        candidate_panel = build_point_in_time_panel(
            facts,
            frozen,
            macro,
            macro_config,
            cutoff=pd.Timestamp(policy["financial_history_cutoff"]).date(),
        )
    targets = {sector: int(value) for sector, value in policy["target_count_by_sector"].items()}
    base_version = str(frozen["universe_version"].iloc[0])
    rules, certification = certify_panel(candidate_panel, universe_version=base_version)
    # Persist complete certification evidence before assigning quality tiers.
    # Phase 2 retains the frozen selected universe rather than replacing firms
    # that fail the stricter Phase 1 all-KPI company gate.
    candidate_panel.to_parquet(
        paths.interim / "phase2_candidate_point_in_time_panel.parquet", index=False
    )
    rules.to_parquet(paths.interim / "phase2_candidate_certification_rules.parquet", index=False)
    certification.to_csv(paths.reports / "phase2_candidate_certification_summary.csv", index=False)
    final_universe = frozen.loc[frozen["selection_status"] == "SELECTED"].copy()
    replacements = pd.DataFrame(
        columns=[
            "sector",
            "removed_cik",
            "replacement_cik",
            "replacement_rank",
            "replacement_source",
            "failed_rules",
            "outcome_information_used",
        ]
    )
    certification_lookup = certification.set_index("cik")
    final_universe["strict_phase1_certified"] = final_universe["cik"].map(
        certification_lookup["certified"]
    )
    final_universe["certification_failed_rules"] = final_universe["cik"].map(
        certification_lookup["failed_rules"]
    )
    final_universe["quality_tier"] = final_universe["strict_phase1_certified"].map(
        {True: "STRICT_PHASE1_CERTIFIED", False: "PHASE2_RETAINED_WITH_QUALITY_FLAG"}
    )
    final_ciks = set(final_universe["cik"].astype(str))
    final_panel = candidate_panel.loc[candidate_panel["cik"].isin(final_ciks)].copy()
    final_panel["company_quarter_interest_coverage_eligible"] = (
        final_panel["interest_coverage_ttm"].notna()
        & final_panel["operating_income_ttm"].notna()
        & final_panel["interest_expense_ttm"].gt(0)
    )
    final_panel["company_quarter_lineage_eligible"] = (
        final_panel["maximum_source_available_at"].le(final_panel["decision_at"])
        & final_panel["accession_numbers_json"].notna()
    )
    lineage_metadata = final_universe[
        [
            "cik",
            "exchange",
            "selection_as_of",
            "strict_phase1_certified",
            "certification_failed_rules",
            "quality_tier",
        ]
    ].copy()
    final_panel = final_panel.merge(lineage_metadata, on="cik", how="left", validate="many_to_one")
    final_facts = facts.loc[facts["cik"].isin(final_ciks)].copy()
    final_certification = certification.loc[certification["cik"].isin(final_ciks)].copy()
    expected_total = sum(targets.values())
    final_sector_counts = final_universe.groupby("sector")["cik"].nunique().to_dict()
    if len(final_certification) != expected_total or final_sector_counts != targets:
        raise ValueError(f"Final Phase 2 universe does not match confirmed targets {targets}")
    final_universe.to_parquet(paths.processed / "phase2_selected_universe.parquet", index=False)
    final_panel.to_parquet(paths.processed / "phase2_point_in_time_panel.parquet", index=False)
    final_facts.to_parquet(paths.processed / "phase2_financial_facts_final.parquet", index=False)
    rules.to_parquet(paths.processed / "phase2_certification_rules.parquet", index=False)
    final_certification.to_csv(paths.reports / "phase2_certification_summary.csv", index=False)
    replacements.to_csv(paths.reports / "phase2_universe_replacements.csv", index=False)
    result = {
        "status": "complete",
        "universe_version": f"{base_version}-company-quarter-eligible",
        "retained_companies": len(final_certification),
        "strict_phase1_certified_companies": int(final_certification["certified"].sum()),
        "retained_with_quality_flag": int((~final_certification["certified"]).sum()),
        "sector_counts": final_sector_counts,
        "replacements": len(replacements),
        "point_in_time_rows": len(final_panel),
        "financial_fact_rows": len(final_facts),
        "synthetic_data_used": False,
        "outcome_or_model_information_used_for_replacement": False,
        "replacement_attempted": False,
        "strict_certification_is_quality_tier_not_exclusion_gate": True,
        "company_quarter_eligibility_is_modeling_gate": True,
    }
    (paths.reports / "stage24_summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result
