"""Phase 1 asset graph scaffolding.

Only the configuration and database foundation assets are immediately materializable. Network
and modeling assets are declared as observable placeholders so the intended lineage is explicit
without pretending unimplemented transformations already work.
"""

from typing import Any

from dagster import AssetExecutionContext, MaterializeResult, MetadataValue, asset

from cfd.config import load_project_config
from cfd.database import initialize_database


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
def sec_company_universe() -> None:
    """Candidate issuer metadata; implemented in the SEC proof-of-concept milestone."""

    raise NotImplementedError("Run the documented SEC proof-of-concept milestone first")


@asset(deps=[sec_company_universe], group_name="source_data")
def sec_as_filed_fundamentals() -> None:
    """As-filed, accession-aware quarterly financial facts."""

    raise NotImplementedError("Financial statement bulk ingestion is the next milestone")


@asset(deps=[local_duckdb], group_name="source_data")
def alfred_macro_vintages() -> None:
    """Point-in-time macro observations with real-time periods."""

    raise NotImplementedError("ALFRED ingestion requires a configured free FRED_API_KEY")


@asset(deps=[sec_as_filed_fundamentals], group_name="analytics")
def normalized_company_quarters() -> None:
    raise NotImplementedError("Requires source financial facts")


@asset(deps=[normalized_company_quarters, alfred_macro_vintages], group_name="analytics")
def point_in_time_feature_table() -> None:
    raise NotImplementedError("Requires normalized financial and macro inputs")


@asset(deps=[point_in_time_feature_table], group_name="modeling")
def kpi_forecasts() -> None:
    raise NotImplementedError("Requires the leakage-safe feature table")


@asset(deps=[point_in_time_feature_table, kpi_forecasts], group_name="modeling")
def deterioration_predictions() -> None:
    raise NotImplementedError("Requires time-aware model training")


@asset(deps=[deterioration_predictions], group_name="delivery")
def tableau_exports() -> None:
    raise NotImplementedError("Requires out-of-fold predictions and KPI forecasts")
