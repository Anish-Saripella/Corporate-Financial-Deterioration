"""Stage 8 certification, deterministic replacements, and final local-store materialization."""

from __future__ import annotations

import hashlib
import json
import shutil
from typing import Any, cast

import duckdb
import pandas as pd
import yaml

from cfd.config import read_yaml, repository_root
from cfd.manifest import write_existing_file_manifest
from cfd.panel import certify_panel


def _excluded_ciks() -> set[str]:
    config = read_yaml(repository_root() / "configs" / "sic_mapping.yml")
    return {
        str(row["cik"]).zfill(10) for row in config.get("entity_overrides", {}).get("exclude", [])
    }


def choose_replacements(
    selected_metadata: pd.DataFrame,
    selected_summary: pd.DataFrame,
    pool_metadata: pd.DataFrame,
    pool_summary: pd.DataFrame,
    frozen_config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Replace failures by frozen reserves first, then deterministic candidate scores."""

    for frame in [selected_metadata, selected_summary, pool_metadata, pool_summary]:
        frame["cik"] = frame["cik"].astype(str).str.zfill(10)
    certified_pool = pool_summary.loc[pool_summary["certified"]].merge(
        pool_metadata, on=["cik", "company_name", "ticker", "sector"], how="left"
    )
    certified_pool = certified_pool.loc[~certified_pool["cik"].isin(_excluded_ciks())]
    reserve_order = {
        str(row["cik"]).zfill(10): position
        for position, row in enumerate(frozen_config.get("reserve", []), start=1)
    }
    certified_pool["frozen_reserve_order"] = certified_pool["cik"].map(reserve_order)
    certified_pool["is_frozen_reserve"] = certified_pool["frozen_reserve_order"].notna()
    certified_pool = certified_pool.sort_values(
        ["sector", "is_frozen_reserve", "frozen_reserve_order", "random_score", "cik"],
        ascending=[True, False, True, True, True],
    )

    failed = selected_summary.loc[~selected_summary["certified"]].merge(
        selected_metadata[["cik", "random_rank"]], on="cik", how="left"
    )
    failed = failed.sort_values(["sector", "random_rank", "cik"])
    replacements: list[dict[str, Any]] = []
    chosen_ciks: set[str] = set()
    for sector, sector_failed in failed.groupby("sector", sort=True):
        options = certified_pool.loc[
            (certified_pool["sector"] == sector) & ~certified_pool["cik"].isin(chosen_ciks)
        ]
        if len(options) < len(sector_failed):
            raise ValueError(
                f"Insufficient certified replacements for {sector}: "
                f"need {len(sector_failed)}, have {len(options)}"
            )
        selected_options = options.head(len(sector_failed))
        for removed, replacement in zip(
            sector_failed.itertuples(index=False),
            selected_options.itertuples(index=False),
            strict=True,
        ):
            removed = cast(Any, removed)
            replacement = cast(Any, replacement)
            chosen_ciks.add(str(replacement.cik))
            replacements.append(
                {
                    "resulting_universe_version": "selected-universe-v2-certified",
                    "removed_cik": str(removed.cik),
                    "removed_ticker": str(removed.ticker),
                    "replacement_cik": str(replacement.cik),
                    "replacement_ticker": str(replacement.ticker),
                    "sector": str(sector),
                    "failed_rule_code": str(removed.failed_rules),
                    "replacement_rank": int(removed.random_rank),
                    "replacement_source": (
                        "frozen_reserve"
                        if bool(replacement.is_frozen_reserve)
                        else "deterministic_expanded_candidate_pool"
                    ),
                    "decided_at": "2026-08-02",
                }
            )
    replacement_audit = pd.DataFrame(replacements)
    retained = selected_metadata.loc[
        ~selected_metadata["cik"].isin(replacement_audit["removed_cik"])
    ].copy()
    replacement_rows = pool_metadata.loc[
        pool_metadata["cik"].isin(replacement_audit["replacement_cik"])
    ].copy()
    slots = replacement_audit.set_index("replacement_cik")["replacement_rank"]
    replacement_rows["random_rank"] = replacement_rows["cik"].map(slots)
    replacement_rows["selection_status"] = "SELECTED"
    final = pd.concat([retained, replacement_rows], ignore_index=True, sort=False)
    final["selection_status"] = "SELECTED"
    if len(final) != 60 or set(final.groupby("sector").size()) != {30}:
        raise ValueError("Replacement process did not preserve the 30/30 final universe")
    return replacement_audit, final


def assign_size_tiers(final: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    development = panel.loc[panel["decision_at"] < pd.Timestamp("2024-01-01")]
    proxies = development.groupby("cik", as_index=False).agg(
        median_total_assets=("total_assets", "median"), median_revenue=("revenue_ttm", "median")
    )
    result = final.drop(
        columns=["size_tier", "median_total_assets", "median_revenue"], errors="ignore"
    )
    result = result.merge(proxies, on="cik", how="left", validate="one_to_one")
    labels = ["small", "medium", "large"]
    result["size_tier"] = result.groupby("sector")["median_total_assets"].transform(
        lambda values: pd.qcut(values.rank(method="first"), 3, labels=labels)
    )
    return result


def _freeze_universe(final: pd.DataFrame, replacement_audit: pd.DataFrame) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    replacement_map = replacement_audit.set_index("replacement_cik").to_dict("index")
    for row in final.sort_values(["sector", "random_rank"]).itertuples(index=False):
        row = cast(Any, row)
        entry: dict[str, Any] = {
            "cik": str(row.cik),
            "ticker": str(row.ticker),
            "sector": str(row.sector),
            "industry": str(row.industry),
            "size_tier": str(row.size_tier),
            "random_rank": int(row.random_rank),
        }
        replacement = replacement_map.get(str(row.cik))
        if replacement:
            entry["replaces_cik"] = str(replacement["removed_cik"])
            entry["replacement_source"] = str(replacement["replacement_source"])
        rows.append(entry)
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return {
        "version": "selected-universe-v2-certified",
        "selection_as_of": "2026-08-02",
        "financial_history_cutoff": "2025-12-31",
        "certification_config": "point-in-time-panel-v1",
        "random_seed": 20260802,
        "manifest_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "selected": rows,
        "reserve": [],
        "notes": [
            "Every selected company passed all three Stage 8 KPI and lineage gates.",
            "Replacements used frozen same-sector reserves first, then deterministic "
            "candidate scores.",
            "No deterioration labels, event prevalence, or model results influenced replacement.",
            "No certified unused Utilities reserves remain under the current strict rules.",
        ],
    }


def materialize_certified_universe(
    selected_facts: pd.DataFrame,
    selected_panel: pd.DataFrame,
    selected_summary: pd.DataFrame,
    pool_facts: pd.DataFrame,
    pool_panel: pd.DataFrame,
    pool_summary: pd.DataFrame,
) -> dict[str, Any]:
    root = repository_root()
    processed = root / "data" / "processed"
    interim = root / "data" / "interim"
    reports = root / "reports" / "generated"
    selected_metadata = pd.read_parquet(processed / "selected_universe.parquet").query(
        "selection_status == 'SELECTED'"
    )
    pool_metadata = pd.read_parquet(processed / "issuer_candidates.parquet")
    frozen = read_yaml(root / "configs" / "selected_universe.yml")
    audit, final_metadata = choose_replacements(
        selected_metadata, selected_summary, pool_metadata, pool_summary, frozen
    )
    final_ciks = set(final_metadata["cik"])
    combined_facts = pd.concat([selected_facts, pool_facts], ignore_index=True)
    combined_facts = combined_facts.loc[combined_facts["cik"].isin(final_ciks)].copy()
    combined_panel = pd.concat([selected_panel, pool_panel], ignore_index=True)
    combined_panel = combined_panel.loc[combined_panel["cik"].isin(final_ciks)].copy()
    final_metadata = assign_size_tiers(final_metadata, combined_panel)
    metadata_columns = ["cik", "company_name", "ticker", "sector", "industry", "size_tier"]
    combined_panel = combined_panel.drop(
        columns=[column for column in metadata_columns[1:] if column in combined_panel],
        errors="ignore",
    ).merge(final_metadata[metadata_columns], on="cik", how="left", validate="many_to_one")
    rules, summary = certify_panel(
        combined_panel, universe_version="selected-universe-v2-certified"
    )
    if len(summary) != 60 or not summary["certified"].all():
        failures = summary.loc[~summary["certified"], ["ticker", "failed_rules"]].to_dict("records")
        raise ValueError(f"Final universe failed certification: {failures}")

    combined_facts.to_parquet(processed / "financial_facts_raw.parquet", index=False)
    combined_panel.to_parquet(processed / "point_in_time_panel.parquet", index=False)
    rules.to_parquet(processed / "company_modeling_certification.parquet", index=False)
    final_metadata.to_parquet(processed / "selected_universe.parquet", index=False)
    audit.to_parquet(processed / "universe_replacements.parquet", index=False)
    summary.to_csv(reports / "company_certification_summary.csv", index=False)
    audit.to_csv(reports / "universe_replacements.csv", index=False)

    frozen_v2 = _freeze_universe(final_metadata, audit)
    (root / "configs" / "selected_universe.yml").write_text(
        yaml.safe_dump(frozen_v2, sort_keys=False, width=120), encoding="utf-8"
    )

    raw_main = root / "data" / "raw" / "sec" / "companyfacts"
    raw_pool = root / "data" / "raw" / "sec" / "replacement_pool"
    manifests = root / "data" / "manifests"
    for cik in audit["replacement_cik"]:
        source = raw_pool / f"CIK{cik}.json"
        destination = raw_main / source.name
        shutil.copy2(source, destination)
        write_existing_file_manifest(
            path=destination,
            manifest_directory=manifests,
            source="SEC EDGAR",
            url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
            parameters={"purpose": "stage8_certified_replacement"},
        )
    for path in raw_main.glob("CIK*.json"):
        cik = path.stem.removeprefix("CIK")
        if cik not in final_ciks:
            path.unlink()
            manifest = manifests / f"{path.name}.manifest.json"
            if manifest.exists():
                manifest.unlink()
    shutil.rmtree(raw_pool)
    shutil.rmtree(manifests / "replacement_pool")
    (interim / "replacement_pool_financial_facts.parquet").unlink(missing_ok=True)
    (interim / "replacement_pool_panel.parquet").unlink(missing_ok=True)
    (interim / "replacement_pool_certification.parquet").unlink(missing_ok=True)

    with duckdb.connect(str(processed / "cfd.duckdb")) as connection:
        for table, filename in {
            "financial_facts_raw": "financial_facts_raw.parquet",
            "point_in_time_panel": "point_in_time_panel.parquet",
            "company_modeling_certification": "company_modeling_certification.parquet",
            "selected_universe": "selected_universe.parquet",
            "universe_replacements": "universe_replacements.parquet",
        }.items():
            parquet_location = str(processed / filename).replace("'", "''")
            connection.execute(
                f"CREATE OR REPLACE TABLE marts.{table} "
                f"AS SELECT * FROM read_parquet('{parquet_location}')"
            )
    return {
        "status": "complete",
        "universe_version": "selected-universe-v2-certified",
        "certified_companies": 60,
        "sector_counts": final_metadata.groupby("sector").size().to_dict(),
        "replacements": len(audit),
        "replacement_sources": audit["replacement_source"].value_counts().to_dict(),
        "point_in_time_rows": len(combined_panel),
        "financial_fact_rows": len(combined_facts),
        "raw_companyfacts_retained": len(list(raw_main.glob("CIK*.json"))),
    }
