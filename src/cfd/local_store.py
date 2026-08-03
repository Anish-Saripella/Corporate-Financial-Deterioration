"""Materialize and maintain the selected-universe-only local financial store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from cfd.config import ensure_local_directories, load_project_config, read_yaml, repository_root

FINANCIAL_PARQUETS = (
    "financial_facts_raw.parquet",
    "company_fiscal_quarters.parquet",
    "company_quarter_wide.parquet",
)


def load_selected_ciks() -> set[str]:
    """Load exactly the frozen SELECTED CIKs; reserves are intentionally excluded."""

    payload = read_yaml(repository_root() / "configs" / "selected_universe.yml")
    selected = {str(row["cik"]).zfill(10) for row in payload["selected"]}
    expected = load_project_config().scope.final_company_count
    if len(selected) != expected:
        raise ValueError(f"Expected {expected} selected CIKs, found {len(selected)}")
    return selected


def _filter_financial_parquet(path: Path, selected: set[str]) -> dict[str, int]:
    frame = pd.read_parquet(path)
    before_rows = len(frame)
    frame["cik"] = frame["cik"].astype(str).str.zfill(10)
    filtered = frame.loc[frame["cik"].isin(selected)].copy()
    represented = set(filtered["cik"].unique())
    missing = selected - represented
    if missing:
        raise ValueError(f"{path.name} is missing selected CIKs: {sorted(missing)}")
    temporary = path.with_suffix(".parquet.tmp")
    filtered.to_parquet(temporary, index=False)
    temporary.replace(path)
    return {
        "rows_before": before_rows,
        "rows_after": len(filtered),
        "companies_after": len(represented),
    }


def _remove_manifest_for_artifact(manifest_directory: Path, artifact: Path) -> int:
    removed = 0
    for manifest_path in manifest_directory.glob("*.manifest.json"):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if Path(payload.get("output_path", "")) == artifact:
            manifest_path.unlink()
            removed += 1
    return removed


def materialize_final_universe_store() -> dict[str, Any]:
    """Keep local company financial data only for the frozen final universe."""

    config = load_project_config()
    paths = ensure_local_directories(config)
    selected = load_selected_ciks()
    processed = paths["processed"]
    raw_sec = paths["raw"] / "sec"

    parquet_results = {
        filename: _filter_financial_parquet(processed / filename, selected)
        for filename in FINANCIAL_PARQUETS
    }

    companyfacts_dir = raw_sec / "companyfacts"
    selected_raw = {companyfacts_dir / f"CIK{cik}.json" for cik in selected}
    missing_raw = sorted(str(path) for path in selected_raw if not path.exists())
    if missing_raw:
        raise ValueError(f"Selected raw Company Facts files are missing: {missing_raw}")

    removed_raw_files = 0
    removed_manifests = 0
    for path in companyfacts_dir.glob("CIK*.json"):
        if path not in selected_raw:
            removed_manifests += _remove_manifest_for_artifact(paths["manifests"], path)
            path.unlink()
            removed_raw_files += 1

    # Proof financial files and broad-quarter financial archives are redundant after selection.
    proof_root = raw_sec / "proof_of_concept"
    for pattern in ("*-companyfacts.json", "20*q*.zip"):
        for path in proof_root.glob(pattern):
            removed_manifests += _remove_manifest_for_artifact(paths["manifests"], path)
            path.unlink()
            removed_raw_files += 1

    with duckdb.connect(str(paths["duckdb"])) as connection:
        for table, filename in {
            "financial_facts_raw": "financial_facts_raw.parquet",
            "company_fiscal_quarters": "company_fiscal_quarters.parquet",
            "company_quarter_wide": "company_quarter_wide.parquet",
        }.items():
            parquet_path = str(processed / filename).replace("'", "''")
            connection.execute(
                f"CREATE OR REPLACE TABLE marts.{table} "
                f"AS SELECT * FROM read_parquet('{parquet_path}')"
            )

    report = {
        "status": "complete",
        "selected_companies": len(selected),
        "reserves_included": 0,
        "parquet_tables": parquet_results,
        "raw_companyfacts_retained": len(list(companyfacts_dir.glob("CIK*.json"))),
        "raw_financial_files_removed": removed_raw_files,
        "source_manifests_removed": removed_manifests,
        "api_calls_required": 0,
    }
    report_path = repository_root() / "reports" / "generated" / "local_financial_store.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
