"""Materializable local asset graph for the completed Phase 1 modeling pipeline."""

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
from dagster import AssetExecutionContext, MaterializeResult, MetadataValue, asset

from cfd.analysis.model_results import run_model_result_plots
from cfd.config import load_project_config, repository_root
from cfd.database import initialize_database
from cfd.stage13 import run_stage_13
from cfd.stage14 import run_stage_14
from cfd.stage15 import run_stage_15
from cfd.stage16 import finalize_stage_16
from cfd.stage17 import run_stage_17
from cfd.stage18 import run_stage_18


def _table_metadata(path: Path, *, key: str = "decision_key") -> dict[str, Any]:
    frame = pd.read_parquet(path)
    metadata: dict[str, Any] = {
        "path": MetadataValue.path(str(path)),
        "rows": len(frame),
        "columns": len(frame.columns),
    }
    if key in frame:
        metadata["unique_keys"] = int(frame[key].nunique())
    return metadata


@asset(group_name="foundation", description="Validated, version-controlled Phase 1 scope.")
def phase1_configuration(context: AssetExecutionContext) -> MaterializeResult[Any]:
    config = load_project_config()
    context.log.info("Validated project configuration version %s", config.project.version)
    return MaterializeResult(
        metadata={
            "sectors": MetadataValue.json(config.scope.sectors),
            "forecast_kpis": MetadataValue.json(config.scope.forecast_kpis),
            "company_count": config.scope.final_company_count,
            "free_public_data_only": config.source_policy.free_public_only,
        }
    )


@asset(deps=[phase1_configuration], group_name="foundation")
def local_duckdb(context: AssetExecutionContext) -> MaterializeResult[Any]:
    path = initialize_database(load_project_config())
    context.log.info("Initialized DuckDB at %s", path)
    return MaterializeResult(metadata={"path": MetadataValue.path(str(path))})


@asset(deps=[local_duckdb], group_name="source_data")
def certified_local_source_cache() -> MaterializeResult[Any]:
    root = repository_root()
    files = list((root / "data" / "raw" / "sec" / "companyfacts").glob("CIK*.json"))
    if len(files) != 60:
        raise ValueError(f"Expected 60 cached Company Facts files, found {len(files)}")
    return MaterializeResult(metadata={"cached_companyfacts": len(files), "network_calls": 0})


@asset(deps=[certified_local_source_cache], group_name="analytics")
def certified_point_in_time_panel() -> MaterializeResult[Any]:
    path = repository_root() / "data" / "processed" / "point_in_time_panel.parquet"
    frame = pd.read_parquet(path)
    if frame["decision_key"].duplicated().any():
        raise ValueError("Certified panel contains duplicate decision keys")
    if (frame["maximum_source_available_at"] > frame["decision_at"]).any():
        raise ValueError("Certified panel contains future financial information")
    return MaterializeResult(metadata=_table_metadata(path))


@asset(deps=[certified_point_in_time_panel], group_name="analytics")
def frozen_temporal_design() -> MaterializeResult[Any]:
    path = repository_root() / "data" / "processed" / "temporal_split_assignments.parquet"
    return MaterializeResult(metadata=_table_metadata(path))


@asset(deps=[frozen_temporal_design], group_name="modeling")
def kpi_forecasts() -> MaterializeResult[Any]:
    result = run_stage_13()
    return MaterializeResult(metadata={"summary": MetadataValue.json(result)})


@asset(deps=[kpi_forecasts], group_name="modeling")
def deterioration_predictions() -> MaterializeResult[Any]:
    stage14 = run_stage_14()
    stage15 = run_stage_15()
    return MaterializeResult(
        metadata={
            "stage14": MetadataValue.json(stage14),
            "stage15": MetadataValue.json(stage15),
        }
    )


@asset(deps=[deterioration_predictions], group_name="delivery")
def publication_model_diagnostics() -> MaterializeResult[Any]:
    result = run_model_result_plots()
    return MaterializeResult(metadata={"figures": MetadataValue.json(result)})


@asset(deps=[publication_model_diagnostics], group_name="governance")
def production_model_pipeline() -> MaterializeResult[Any]:
    root = repository_root()
    reports = root / "reports" / "generated"

    def load(name: str) -> dict[str, Any]:
        payload = json.loads((reports / name).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a JSON object in {name}")
        return payload

    result = finalize_stage_16(
        stage13=load("stage13_summary.json"),
        stage14=load("stage14_summary.json"),
        stage15=load("stage15_summary.json"),
        plots=run_model_result_plots(),
        started_at=time.monotonic(),
    )
    return MaterializeResult(metadata={"run_manifest": MetadataValue.json(result)})


@asset(deps=[production_model_pipeline], group_name="delivery")
def tableau_dashboard_exports() -> MaterializeResult[Any]:
    result = run_stage_17()
    return MaterializeResult(metadata={"summary": MetadataValue.json(result)})


@asset(deps=[tableau_dashboard_exports], group_name="governance")
def phase1_release_audit() -> MaterializeResult[Any]:
    result = run_stage_18()
    return MaterializeResult(metadata={"summary": MetadataValue.json(result)})
