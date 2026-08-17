"""Stage 21: build the real all-candidate Phase 2 eligibility audit."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from cfd.config import read_yaml, repository_root
from cfd.eligibility import audit_company_eligibility
from cfd.ingestion.sec import SecClient
from cfd.normalization.companyfacts import (
    extract_company_facts,
    normalize_fiscal_quarters,
    quarterly_wide,
)
from cfd.settings import RuntimeSettings
from cfd.stages import stage_paths
from cfd.universe import deterministic_score, issuer_rows_from_submissions_zip, load_sic_rules


def run_stage_21() -> dict[str, Any]:
    """Ingest every mapped active candidate before the balanced sector draw.

    This ordering matters. If financial histories were downloaded only for a
    preferred sample, data availability could influence selection informally.
    Here, every mapped candidate receives the same eligibility audit first.
    """

    root = repository_root()
    paths = stage_paths()
    config = read_yaml(root / "configs" / "phase2.yml")
    policy = config["universe_policy"]
    raw_root = paths.raw_sec / "phase2"
    facts_root = raw_root / "companyfacts"
    manifest_root = paths.manifests / "phase2"
    for directory in [raw_root, facts_root, manifest_root]:
        directory.mkdir(parents=True, exist_ok=True)
    submissions = raw_root / "submissions.zip"
    settings = RuntimeSettings()
    user_agent = settings.require_sec_user_agent()
    submissions_url = "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip"
    with SecClient(user_agent=user_agent) as client:
        if not submissions.exists():
            client.download(
                url=submissions_url,
                destination=submissions,
                manifest_directory=manifest_root,
            )
        mapped = issuer_rows_from_submissions_zip(
            submissions,
            load_sic_rules(root / "configs" / "sic_mapping.yml"),
            filing_history_cutoff=str(policy["financial_history_cutoff"]),
        )
        candidates = mapped.loc[mapped["candidate_eligible"]].copy()
        candidates["selection_as_of"] = pd.Timestamp(policy["selection_as_of"])
        candidates.to_parquet(
            paths.interim / "phase2_mapped_active_candidates.parquet", index=False
        )
        fact_frames: list[pd.DataFrame] = []
        failures: list[dict[str, str]] = []
        concepts = read_yaml(root / "configs" / "sec_tags.yml")["concepts"]
        for row in candidates.sort_values("cik").itertuples(index=False):
            cik = str(row.cik).zfill(10)
            destination = facts_root / f"CIK{cik}.json"
            try:
                if not destination.exists():
                    client.download(
                        url=client.companyfacts_url(cik),
                        destination=destination,
                        manifest_directory=manifest_root,
                    )
                facts = extract_company_facts(
                    json.loads(destination.read_text(encoding="utf-8")), concepts
                )
                if not facts.empty:
                    fact_frames.append(facts)
            except Exception as error:  # a failure is recorded; it never becomes eligibility
                failures.append({"cik": cik, "error_type": type(error).__name__})
    if not fact_frames:
        raise ValueError("No real SEC Company Facts histories were successfully ingested")
    raw_facts = pd.concat(fact_frames, ignore_index=True)
    quarters = normalize_fiscal_quarters(
        raw_facts, cutoff=pd.Timestamp(policy["financial_history_cutoff"]).date()
    )
    wide = quarterly_wide(quarters)
    rules = policy["eligibility_rules"]
    eligibility = audit_company_eligibility(
        candidates,
        wide,
        eligibility_mode="company_quarter",
        minimum_interest_coverage_quarters=int(rules["minimum_interest_coverage_quarters"]),
        minimum_consecutive_interest_coverage_quarters=int(
            rules["minimum_consecutive_interest_coverage_quarters"]
        ),
        minimum_total_assets_quarters=int(rules["minimum_total_assets_quarters"]),
        minimum_interest_expense=float(rules["minimum_meaningful_interest_expense"]),
    )
    eligibility["selection_as_of"] = pd.Timestamp(policy["selection_as_of"])
    eligibility["financial_history_cutoff"] = pd.Timestamp(policy["financial_history_cutoff"])
    eligibility["random_score"] = eligibility["cik"].map(
        lambda cik: deterministic_score(str(cik), int(policy["random_seed"]))
    )
    raw_facts.to_parquet(paths.interim / "phase2_financial_facts_raw.parquet", index=False)
    quarters.to_parquet(paths.interim / "phase2_company_fiscal_quarters.parquet", index=False)
    wide.to_parquet(paths.interim / "phase2_company_quarter_wide.parquet", index=False)
    eligibility.to_parquet(paths.processed / "phase2_company_eligibility.parquet", index=False)
    eligibility.to_csv(paths.reports / "phase2_company_eligibility.csv", index=False)
    (paths.reports / "phase2_ingestion_failures.json").write_text(
        json.dumps(failures, indent=2) + "\n", encoding="utf-8"
    )
    eligible_counts = eligibility.loc[eligibility["eligible"]].groupby("sector")["cik"].nunique()
    targets = {sector: int(value) for sector, value in policy["target_count_by_sector"].items()}
    if any(eligible_counts.get(sector, 0) < target for sector, target in targets.items()):
        raise ValueError(
            f"Real eligibility audit cannot support {targets}: {eligible_counts.to_dict()}"
        )
    return {
        "status": "complete",
        "mapped_active_candidates": len(candidates),
        "companyfacts_histories": len(fact_frames),
        "ingestion_failures": len(failures),
        "eligible_counts": eligible_counts.to_dict(),
        "selection_performed": False,
        "synthetic_data_used": False,
    }
