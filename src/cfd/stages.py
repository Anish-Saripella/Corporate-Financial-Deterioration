"""Executable Stage 0-7 pipeline with persisted audit evidence."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from cfd.config import (
    ensure_local_directories,
    load_project_config,
    read_yaml,
    repository_root,
)
from cfd.eligibility import audit_company_eligibility
from cfd.ingestion.fred import FredClient
from cfd.ingestion.sec import SecClient
from cfd.manifest import verify_manifest, write_existing_file_manifest
from cfd.normalization.companyfacts import (
    extract_company_facts,
    normalize_fiscal_quarters,
    quarterly_wide,
)
from cfd.settings import RuntimeSettings
from cfd.universe import (
    build_candidate_pool,
    issuer_rows_from_submissions_zip,
    load_sic_rules,
    select_final_universe,
)


@dataclass(frozen=True)
class StagePaths:
    root: Path
    raw_sec: Path
    raw_fred: Path
    interim: Path
    processed: Path
    manifests: Path
    reports: Path


def stage_paths() -> StagePaths:
    root = repository_root()
    configured = ensure_local_directories(load_project_config())
    paths = StagePaths(
        root=root,
        raw_sec=configured["raw"] / "sec",
        raw_fred=configured["raw"] / "fred",
        interim=configured["interim"],
        processed=configured["processed"],
        manifests=configured["manifests"],
        reports=root / "reports" / "generated",
    )
    for path in paths.__dict__.values():
        if isinstance(path, Path):
            path.mkdir(parents=True, exist_ok=True)
    return paths


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )


def _manifest_existing_if_needed(path: Path, *, source: str, url: str, manifests: Path) -> None:
    manifest = manifests / f"{path.name}.manifest.json"
    if not manifest.exists():
        write_existing_file_manifest(
            path=path,
            manifest_directory=manifests,
            source=source,
            url=url,
        )


def _sec_download_if_missing(
    client: SecClient,
    *,
    url: str,
    destination: Path,
    manifests: Path,
) -> None:
    if destination.exists():
        _manifest_existing_if_needed(destination, source="SEC EDGAR", url=url, manifests=manifests)
        return
    client.download(url=url, destination=destination, manifest_directory=manifests)


def complete_stage_0() -> dict[str, Any]:
    config = load_project_config()
    required_configs = [
        "project.yml",
        "universe.yml",
        "label.yml",
        "sec_tags.yml",
        "sic_mapping.yml",
        "data_contracts.yml",
        "proof_of_concept.yml",
        "analytical_panel.yml",
        "macro_series.yml",
    ]
    for filename in required_configs:
        read_yaml(repository_root() / "configs" / filename)
    return {
        "status": "complete",
        "scope_version": config.versions.scope,
        "universe_version": config.versions.universe,
        "label_version": config.versions.label,
        "feature_version": config.versions.features,
        "mapping_versions": [config.versions.sec_concept_mapping, config.versions.sic_mapping],
    }


def complete_stage_1(paths: StagePaths) -> dict[str, Any]:
    """Download and validate the documented proof-of-concept source sample."""

    settings = RuntimeSettings()
    proof = read_yaml(paths.root / "configs" / "proof_of_concept.yml")["proof_of_concept"]
    concept_config = read_yaml(paths.root / "configs" / "sec_tags.yml")["concepts"]
    proof_root = paths.raw_sec / "proof_of_concept"
    proof_root.mkdir(parents=True, exist_ok=True)
    facts_summary: list[dict[str, Any]] = []
    proof_accessions: dict[str, set[str]] = {}

    with SecClient(user_agent=settings.require_sec_user_agent()) as client:
        ticker_url = "https://www.sec.gov/files/company_tickers_exchange.json"
        _sec_download_if_missing(
            client,
            url=ticker_url,
            destination=paths.raw_sec / "company_tickers_exchange.json",
            manifests=paths.manifests,
        )
        for company in proof["companies"]:
            cik = str(company["cik"]).zfill(10)
            submissions_path = proof_root / f"CIK{cik}-submissions.json"
            facts_path = proof_root / f"CIK{cik}-companyfacts.json"
            _sec_download_if_missing(
                client,
                url=client.submissions_url(cik),
                destination=submissions_path,
                manifests=paths.manifests,
            )
            _sec_download_if_missing(
                client,
                url=client.companyfacts_url(cik),
                destination=facts_path,
                manifests=paths.manifests,
            )
            facts = extract_company_facts(
                json.loads(facts_path.read_text(encoding="utf-8")), concept_config
            )
            facts_summary.append(
                {
                    "cik": cik,
                    "ticker": company["ticker"],
                    "sector": company["sector"],
                    "earliest_end_date": facts["end_date"].min(),
                    "latest_end_date": facts["end_date"].max(),
                    "configured_concepts_found": int(facts["concept"].nunique()),
                    "accessions_found": int(facts["accession_number"].nunique()),
                }
            )
            proof_accessions[cik] = set(facts["accession_number"].astype(str))
        bulk_paths: list[Path] = []
        for quarter in proof["sec_bulk_reconciliation_quarters"]:
            url = f"https://www.sec.gov/files/dera/data/financial-statement-data-sets/{quarter}.zip"
            bulk_path = proof_root / f"{quarter}.zip"
            _sec_download_if_missing(
                client,
                url=url,
                destination=bulk_path,
                manifests=paths.manifests,
            )
            bulk_paths.append(bulk_path)

    reconciliation_rows: list[dict[str, Any]] = []
    proof_ciks_as_int = {int(cik) for cik in proof_accessions}
    all_companyfacts_accessions = set().union(*proof_accessions.values())
    for bulk_path in bulk_paths:
        with zipfile.ZipFile(bulk_path) as archive:
            submissions = pd.read_csv(
                archive.open("sub.txt"), sep="\t", dtype={"adsh": "string"}, low_memory=False
            )
            matched_submissions = submissions.loc[submissions["cik"].isin(proof_ciks_as_int)]
            bulk_accessions = set(matched_submissions["adsh"].dropna().astype(str))
            overlap = bulk_accessions & all_companyfacts_accessions
            reconciliation_rows.append(
                {
                    "bulk_quarter": bulk_path.stem,
                    "proof_company_filings": len(bulk_accessions),
                    "accessions_matched_to_companyfacts": len(overlap),
                }
            )
    reconciliation = pd.DataFrame(reconciliation_rows)
    if (reconciliation["accessions_matched_to_companyfacts"] == 0).any():
        raise ValueError("A proof SEC bulk quarter has no accession overlap with Company Facts")
    reconciliation.to_csv(paths.interim / "stage1_sec_bulk_reconciliation.csv", index=False)

    fred_summary: list[dict[str, Any]] = []
    with FredClient(api_key=settings.require_fred_api_key()) as client:
        for kind, series_id in proof["fred_validation_series"].items():
            destination = paths.raw_fred / f"proof_{series_id}.json"
            if not destination.exists():
                vintage_required = kind == "revised"
                client.download_observations(
                    series_id=series_id,
                    destination=destination,
                    manifest_directory=paths.manifests,
                    realtime_start="2012-01-01" if vintage_required else date.today().isoformat(),
                    realtime_end=date.today().isoformat(),
                    output_type=4 if vintage_required else 1,
                )
            payload = json.loads(destination.read_text(encoding="utf-8"))
            observations = payload["observations"]
            fred_summary.append(
                {
                    "series_id": series_id,
                    "kind": kind,
                    "observations": len(observations),
                    "has_realtime_fields": all(
                        "realtime_start" in row and "realtime_end" in row
                        for row in observations[:100]
                    ),
                }
            )

    summary_frame = pd.DataFrame(facts_summary)
    if summary_frame["earliest_end_date"].max().year > 2012:
        raise ValueError("Proof companies do not establish required historical depth")
    if summary_frame["configured_concepts_found"].min() < 5:
        raise ValueError("A proof company exposes fewer than five configured financial concepts")
    if not all(item["has_realtime_fields"] for item in fred_summary):
        raise ValueError("FRED proof data are missing real-time availability fields")
    summary_frame.to_csv(paths.interim / "stage1_companyfacts_summary.csv", index=False)
    return {
        "status": "complete",
        "companies": len(facts_summary),
        "bulk_quarters": proof["sec_bulk_reconciliation_quarters"],
        "bulk_reconciliation": reconciliation_rows,
        "fred_series": fred_summary,
    }


def complete_stage_2(paths: StagePaths) -> dict[str, Any]:
    contracts = read_yaml(paths.root / "configs" / "data_contracts.yml")
    expected_tables = {
        "issuer_candidates",
        "financial_facts_raw",
        "company_fiscal_quarters",
        "macro_vintages",
        "company_eligibility",
        "selected_universe",
    }
    actual_tables = set(contracts["tables"])
    if actual_tables != expected_tables:
        raise ValueError(
            f"Data contracts missing tables: {sorted(expected_tables - actual_tables)}"
        )
    return {
        "status": "complete",
        "contract_version": contracts["version"],
        "tables": sorted(actual_tables),
        "reason_codes": contracts["reason_codes"],
    }


def complete_stage_3(paths: StagePaths) -> tuple[dict[str, Any], pd.DataFrame]:
    config = load_project_config()
    archive = paths.raw_sec / "bulk" / "submissions.zip"
    if not archive.exists():
        raise FileNotFoundError(f"Required SEC submissions archive is missing: {archive}")
    _manifest_existing_if_needed(
        archive,
        source="SEC EDGAR",
        url="https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip",
        manifests=paths.manifests,
    )
    rules = load_sic_rules(paths.root / "configs" / "sic_mapping.yml")
    universe_config = read_yaml(paths.root / "configs" / "universe.yml")["universe"]
    mapped = issuer_rows_from_submissions_zip(
        archive,
        rules,
        filing_history_cutoff=str(universe_config["financial_history_cutoff"]),
    )
    mapped.to_parquet(paths.interim / "mapped_current_issuers.parquet", index=False)
    candidate_pool = build_candidate_pool(
        mapped,
        per_sector=75,
        seed=config.project.random_seed,
    )
    candidate_pool["selection_as_of"] = universe_config["selection_as_of"]
    candidate_pool.to_parquet(paths.processed / "issuer_candidates.parquet", index=False)
    candidate_pool.to_csv(paths.reports / "issuer_candidates.csv", index=False)
    sector_counts = candidate_pool.groupby("sector")["cik"].nunique().to_dict()
    if sum(sector_counts.values()) < 100 or sum(sector_counts.values()) > 150:
        raise ValueError(f"Candidate pool outside configured 100-150 range: {sector_counts}")
    return (
        {
            "status": "complete",
            "mapped_current_issuers": len(mapped),
            "candidate_count": len(candidate_pool),
            "sector_counts": sector_counts,
        },
        candidate_pool,
    )


def _extract_candidate_submission_files(
    *, archive: Path, candidates: pd.DataFrame, destination: Path, manifests: Path
) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        for cik in candidates["cik"]:
            member = f"CIK{str(cik).zfill(10)}.json"
            output = destination / member
            if not output.exists():
                with source.open(member) as source_handle, output.open("wb") as destination_handle:
                    shutil.copyfileobj(source_handle, destination_handle)
            _manifest_existing_if_needed(
                output,
                source="SEC EDGAR bulk submissions",
                url="https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip",
                manifests=manifests,
            )


def complete_stage_4(
    paths: StagePaths, candidates: pd.DataFrame
) -> tuple[dict[str, Any], pd.DataFrame]:
    settings = RuntimeSettings()
    concept_config = read_yaml(paths.root / "configs" / "sec_tags.yml")["concepts"]
    archive = paths.raw_sec / "bulk" / "submissions.zip"
    submission_dir = paths.raw_sec / "submissions"
    companyfacts_dir = paths.raw_sec / "companyfacts"
    companyfacts_dir.mkdir(parents=True, exist_ok=True)
    _extract_candidate_submission_files(
        archive=archive,
        candidates=candidates,
        destination=submission_dir,
        manifests=paths.manifests,
    )

    all_facts: list[pd.DataFrame] = []
    failures: list[dict[str, str]] = []
    with SecClient(user_agent=settings.require_sec_user_agent()) as client:
        for row in candidates.itertuples(index=False):
            cik = str(row.cik).zfill(10)
            destination = companyfacts_dir / f"CIK{cik}.json"
            try:
                _sec_download_if_missing(
                    client,
                    url=client.companyfacts_url(cik),
                    destination=destination,
                    manifests=paths.manifests,
                )
                facts = extract_company_facts(
                    json.loads(destination.read_text(encoding="utf-8")), concept_config
                )
                if not facts.empty:
                    all_facts.append(facts)
            except (
                Exception
            ) as error:  # retained in audit output; one issuer must not abort the batch
                failures.append({"cik": cik, "error_type": type(error).__name__})

    if not all_facts:
        raise ValueError("No candidate financial facts were ingested")
    facts_frame = pd.concat(all_facts, ignore_index=True)
    facts_frame.to_parquet(paths.processed / "financial_facts_raw.parquet", index=False)

    macro_config = read_yaml(paths.root / "configs" / "macro_series.yml")["macro_series"]
    macro_rows: list[dict[str, Any]] = []
    with FredClient(api_key=settings.require_fred_api_key()) as client:
        for series in macro_config:
            series_id = series["series_id"]
            destination = paths.raw_fred / f"{series_id}.json"
            if not destination.exists():
                vintage_required = bool(series["vintage_required"])
                client.download_observations(
                    series_id=series_id,
                    destination=destination,
                    manifest_directory=paths.manifests,
                    realtime_start="2012-01-01" if vintage_required else date.today().isoformat(),
                    realtime_end=date.today().isoformat(),
                    output_type=4 if vintage_required else 1,
                )
            payload = json.loads(destination.read_text(encoding="utf-8"))
            for observation in payload["observations"]:
                value = observation.get("value")
                macro_rows.append(
                    {
                        "series_id": series_id,
                        "observation_date": observation.get("date"),
                        "realtime_start": observation.get("realtime_start"),
                        "realtime_end": observation.get("realtime_end"),
                        "value": None if value in {None, "."} else float(value),
                    }
                )
    macro_frame = pd.DataFrame(macro_rows)
    macro_frame.to_parquet(paths.processed / "macro_vintages.parquet", index=False)
    _write_json(paths.reports / "stage4_ingestion_failures.json", failures)
    return (
        {
            "status": "complete",
            "candidate_companyfacts_files": len(all_facts),
            "candidate_failures": failures,
            "financial_fact_rows": len(facts_frame),
            "macro_rows": len(macro_frame),
            "macro_series": int(macro_frame["series_id"].nunique()),
        },
        facts_frame,
    )


def complete_stage_5(paths: StagePaths, facts: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    cutoff = load_project_config().scope.end_date
    quarters = normalize_fiscal_quarters(facts, cutoff=cutoff)
    if quarters.empty:
        raise ValueError("Fiscal-quarter normalization produced no rows")
    if (quarters["filed_at"] < quarters["end_date"]).any():
        raise ValueError("Normalized facts contain filings before period end")
    duplicates = quarters.duplicated(["cik", "fiscal_year", "fiscal_quarter", "concept"]).sum()
    if duplicates:
        raise ValueError(f"Normalized facts contain {duplicates} duplicate grain rows")
    quarters.to_parquet(paths.processed / "company_fiscal_quarters.parquet", index=False)
    wide = quarterly_wide(quarters)
    wide.to_parquet(paths.processed / "company_quarter_wide.parquet", index=False)
    coverage = (
        quarters.groupby("concept")["cik"]
        .nunique()
        .sort_values(ascending=False)
        .rename("company_count")
        .reset_index()
    )
    coverage.to_csv(paths.reports / "normalized_concept_coverage.csv", index=False)
    return (
        {
            "status": "complete",
            "normalized_fact_rows": len(quarters),
            "company_quarter_rows": len(wide),
            "companies": int(wide["cik"].nunique()),
            "derived_rows": int(quarters["is_derived"].sum()),
            "duplicate_grain_rows": int(duplicates),
        },
        wide,
    )


def complete_stage_6(
    paths: StagePaths, candidates: pd.DataFrame, wide: pd.DataFrame
) -> tuple[dict[str, Any], pd.DataFrame]:
    audit = audit_company_eligibility(candidates, wide)
    audit.to_parquet(paths.processed / "company_eligibility.parquet", index=False)
    audit.to_csv(paths.reports / "company_eligibility.csv", index=False)
    eligible = audit.loc[audit["eligible"]].copy()
    sector_counts = eligible.groupby("sector")["cik"].nunique().to_dict()
    if any(sector_counts.get(sector, 0) < 30 for sector in candidates["sector"].unique()):
        raise ValueError(f"Insufficient eligible issuers for final selection: {sector_counts}")
    return (
        {
            "status": "complete",
            "eligible_companies": len(eligible),
            "sector_counts": sector_counts,
            "median_usable_quarters": float(audit["usable_quarters"].median()),
            "median_core_field_coverage": float(audit["core_field_coverage"].median()),
        },
        eligible,
    )


def complete_stage_7(paths: StagePaths, eligible: pd.DataFrame) -> dict[str, Any]:
    config = load_project_config()
    selected = select_final_universe(
        eligible,
        per_sector=30,
        seed=config.project.random_seed,
    )
    selected.to_parquet(paths.processed / "selected_universe.parquet", index=False)
    selected.to_csv(paths.reports / "selected_universe_and_reserves.csv", index=False)
    final = selected.loc[selected["selection_status"] == "SELECTED"].copy()
    final.to_csv(paths.reports / "selected_60_companies.csv", index=False)
    reproduced = select_final_universe(
        eligible,
        per_sector=30,
        seed=config.project.random_seed,
    )
    columns = ["cik", "selection_status", "random_rank"]
    deterministic = (
        selected[columns].reset_index(drop=True).equals(reproduced[columns].reset_index(drop=True))
    )
    sector_counts = final.groupby("sector")["cik"].nunique().to_dict()
    if len(final) != 60 or set(sector_counts.values()) != {30} or not deterministic:
        raise ValueError(
            f"Final universe gate failed: total={len(final)}, sectors={sector_counts}, "
            f"deterministic={deterministic}"
        )
    frozen_path = paths.root / "configs" / "selected_universe.yml"
    frozen_matches = False
    if frozen_path.exists():
        frozen = read_yaml(frozen_path)
        frozen_rows = [
            {**row, "selection_status": status}
            for status, key in [("SELECTED", "selected"), ("RESERVE", "reserve")]
            for row in frozen[key]
        ]
        generated_key = sorted(
            (
                str(row.cik).zfill(10),
                str(row.ticker),
                str(row.selection_status),
                int(str(row.random_rank)),
            )
            for row in selected.itertuples(index=False)
        )
        frozen_key = sorted(
            (
                str(row["cik"]).zfill(10),
                str(row["ticker"]),
                str(row["selection_status"]),
                int(row["random_rank"]),
            )
            for row in frozen_rows
        )
        ordered = selected.sort_values(["selection_status", "sector", "random_rank"])
        payload = "".join(
            f"{row.cik},{row.ticker},{row.selection_status},{int(str(row.random_rank))}\n"
            for row in ordered.itertuples(index=False)
        )
        manifest_hash = hashlib.sha256(payload.encode()).hexdigest()
        frozen_matches = generated_key == frozen_key and manifest_hash == frozen["manifest_sha256"]
        if not frozen_matches:
            raise ValueError("Generated selection does not match configs/selected_universe.yml")
    return {
        "status": "complete",
        "selected_companies": len(final),
        "reserve_companies": int((selected["selection_status"] == "RESERVE").sum()),
        "sector_counts": sector_counts,
        "deterministic_reproduction": deterministic,
        "random_seed": config.project.random_seed,
        "frozen_manifest_matches": frozen_matches,
    }


def _persist_duckdb(paths: StagePaths) -> None:
    tables = {
        "issuer_candidates": paths.processed / "issuer_candidates.parquet",
        "financial_facts_raw": paths.processed / "financial_facts_raw.parquet",
        "company_fiscal_quarters": paths.processed / "company_fiscal_quarters.parquet",
        "macro_vintages": paths.processed / "macro_vintages.parquet",
        "company_eligibility": paths.processed / "company_eligibility.parquet",
        "selected_universe": paths.processed / "selected_universe.parquet",
    }
    with duckdb.connect(str(paths.processed / "cfd.duckdb")) as connection:
        for name, parquet_path in tables.items():
            if parquet_path.exists():
                escaped = str(parquet_path).replace("'", "''")
                connection.execute(
                    f"CREATE OR REPLACE TABLE marts.{name} "
                    f"AS SELECT * FROM read_parquet('{escaped}')"
                )


def validate_persisted_contracts(paths: StagePaths) -> dict[str, Any]:
    contracts = read_yaml(paths.root / "configs" / "data_contracts.yml")["tables"]
    parquet_files = {
        "issuer_candidates": paths.processed / "issuer_candidates.parquet",
        "financial_facts_raw": paths.processed / "financial_facts_raw.parquet",
        "company_fiscal_quarters": paths.processed / "company_fiscal_quarters.parquet",
        "macro_vintages": paths.processed / "macro_vintages.parquet",
        "company_eligibility": paths.processed / "company_eligibility.parquet",
        "selected_universe": paths.processed / "selected_universe.parquet",
    }
    evidence: dict[str, Any] = {}
    for table, path in parquet_files.items():
        frame = pd.read_parquet(path)
        required = set(contracts[table]["required_columns"])
        primary_key = list(contracts[table]["primary_key"])
        missing = required - set(frame.columns)
        duplicates = int(frame.duplicated(primary_key).sum())
        if missing or duplicates:
            raise ValueError(
                f"Contract failure for {table}: missing={sorted(missing)}, duplicates={duplicates}"
            )
        evidence[table] = {
            "rows": len(frame),
            "required_columns_present": True,
            "duplicate_primary_keys": duplicates,
        }
    return evidence


def verify_source_manifests(paths: StagePaths | None = None) -> dict[str, Any]:
    """Re-hash every cached source represented by an acquisition manifest."""

    resolved = paths or stage_paths()
    manifest_paths = sorted(resolved.manifests.glob("*.manifest.json"))
    results = [verify_manifest(path) for path in manifest_paths]
    failures = [result for result in results if not result["valid"]]
    evidence = {
        "manifest_count": len(results),
        "valid_count": len(results) - len(failures),
        "failure_count": len(failures),
        "failures": failures,
    }
    if failures:
        raise ValueError(f"Source-manifest validation failed: {failures[:3]}")
    return evidence


def run_stages_0_to_7(*, refresh_universe: bool = False) -> dict[str, Any]:
    paths = stage_paths()
    final_store_report = paths.reports / "local_financial_store.json"
    if final_store_report.exists() and not refresh_universe:
        raise RuntimeError(
            "The selected-universe-only store is active. Use the local Parquet/DuckDB data for "
            "modeling. Pass --refresh-universe only when deliberately rebuilding eligibility and "
            "selection, because that operation can download candidate Company Facts histories."
        )
    summary: dict[str, Any] = {"stage_0": complete_stage_0()}
    summary["stage_1"] = complete_stage_1(paths)
    summary["stage_2"] = complete_stage_2(paths)
    summary["stage_3"], candidates = complete_stage_3(paths)
    summary["stage_4"], facts = complete_stage_4(paths, candidates)
    summary["stage_5"], wide = complete_stage_5(paths, facts)
    summary["stage_6"], eligible = complete_stage_6(paths, candidates, wide)
    summary["stage_7"] = complete_stage_7(paths, eligible)
    _persist_duckdb(paths)
    summary["contract_validation"] = validate_persisted_contracts(paths)
    summary["source_manifest_validation"] = verify_source_manifests(paths)
    _write_json(paths.reports / "stages_0_7_summary.json", summary)
    return summary
