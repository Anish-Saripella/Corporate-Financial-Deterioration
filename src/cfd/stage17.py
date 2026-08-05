"""Stage 17 Power BI delivery extracts and publication reconciliation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from cfd.config import repository_root

KPI_COLUMNS = [
    "interest_coverage_ttm",
    "free_cash_flow_margin_ttm",
    "total_debt_to_assets",
]
FORECAST_COLUMNS = [
    "forecast_interest_coverage_4q",
    "forecast_interest_coverage_change_4q",
    "forecast_interest_coverage_uncertainty_4q",
    "forecast_free_cash_flow_margin_4q",
    "forecast_free_cash_flow_margin_change_4q",
    "forecast_free_cash_flow_margin_uncertainty_4q",
    "forecast_total_debt_to_assets_4q",
    "forecast_total_debt_to_assets_change_4q",
    "forecast_total_debt_to_assets_uncertainty_4q",
]


def _risk_band(probability: pd.Series) -> pd.Series:
    return pd.cut(
        probability,
        bins=[-np.inf, 0.15, 0.30, 0.50, np.inf],
        labels=["Low", "Moderate", "High", "Severe"],
    ).astype("string")


def _risk_reason(frame: pd.DataFrame) -> pd.Series:
    conditions = [
        frame["interest_coverage_ttm"].lt(1.5),
        frame["forecast_interest_coverage_change_4q"].lt(0),
        frame["free_cash_flow_margin_ttm"].lt(0),
        frame["total_debt_to_assets_sector_percentile"].ge(0.80),
    ]
    choices = [
        "Coverage below 1.5x",
        "Coverage forecast declining",
        "Negative free cash flow margin",
        "Leverage in highest sector quintile",
    ]
    return pd.Series(
        np.select(conditions, choices, default="No single rule dominates"), index=frame.index
    )


def _champion_predictions(root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    processed = root / "data" / "processed"
    reports = root / "reports" / "generated"
    champion = json.loads((reports / "champion_selection_frozen.json").read_text())
    oof = pd.read_parquet(processed / "classifier_oof_predictions.parquet")
    oof = oof.loc[
        oof["model"].eq(champion["model"])
        & oof["feature_increment"].eq(champion["feature_increment"])
    ].copy()
    oof["evaluation_sample"] = "OOF development backtest"
    holdout = pd.read_parquet(processed / "final_holdout_predictions.parquet").copy()
    holdout["fold_id"] = "final_holdout"
    holdout["evaluation_sample"] = "Locked final holdout"
    predictions = pd.concat([oof, holdout], ignore_index=True)
    if predictions.duplicated(["decision_key", "evaluation_sample"]).any():
        raise ValueError("Stage 17 predictions contain duplicate evaluation keys")
    return predictions, champion


def _watchlist(features: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    identity = [
        "decision_key",
        "cik",
        "decision_at",
        "period_end",
        "sector",
        "industry",
        *KPI_COLUMNS,
        "interest_coverage_ttm_sector_percentile",
        "free_cash_flow_margin_ttm_sector_percentile",
        "total_debt_to_assets_sector_percentile",
        *FORECAST_COLUMNS,
    ]
    latest_prediction = (
        predictions.sort_values("decision_at").groupby("cik", as_index=False).tail(1)
    )
    result = latest_prediction.merge(
        features[identity], on=["decision_key", "cik", "decision_at", "sector"]
    )
    universe = pd.read_parquet(
        repository_root() / "data" / "processed" / "selected_universe.parquet"
    )
    result = result.merge(
        universe[["cik", "company_name", "ticker", "size_tier"]], on="cik", how="left"
    )
    result["risk_band"] = _risk_band(result["probability"])
    result["risk_reason"] = _risk_reason(result)
    result["sector_risk_percentile"] = result.groupby("sector")["probability"].rank(pct=True)
    result["portfolio_risk_rank"] = result["probability"].rank(ascending=False, method="min")
    result["actual_outcome_available"] = result["deterioration_label"].notna()
    result["data_freshness_date"] = result["decision_at"].max()
    return result.sort_values("probability", ascending=False).reset_index(drop=True)


def _portfolio_overview(watchlist: pd.DataFrame) -> pd.DataFrame:
    grouped = watchlist.groupby("sector", dropna=False)
    result = grouped.agg(
        monitored_companies=("cik", "nunique"),
        alerts=("alert", "sum"),
        average_risk_probability=("probability", "mean"),
        median_interest_coverage_x=("interest_coverage_ttm", "median"),
        median_free_cash_flow_margin=("free_cash_flow_margin_ttm", "median"),
        median_debt_to_assets=("total_debt_to_assets", "median"),
        observed_events=("deterioration_label", "sum"),
        observed_outcomes=("deterioration_label", "count"),
    ).reset_index()
    result.insert(0, "snapshot_as_of", watchlist["decision_at"].max())
    result["alert_rate"] = result["alerts"] / result["monitored_companies"]
    result["observed_event_rate"] = result["observed_events"] / result["observed_outcomes"].replace(
        0, np.nan
    )
    result["evaluation_note"] = "Latest evaluated prediction per company; no in-sample scores"
    return result


def _company_history(features: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    universe = pd.read_parquet(
        repository_root() / "data" / "processed" / "selected_universe.parquet"
    )
    identity = universe[["cik", "company_name", "ticker", "size_tier"]]
    pred = predictions[
        [
            "decision_key",
            "probability",
            "threshold",
            "alert",
            "fold_id",
            "evaluation_sample",
        ]
    ]
    columns = [
        "decision_key",
        "cik",
        "decision_at",
        "period_end",
        "sector",
        "industry",
        "deterioration_label",
        "deterioration_episode_start",
        *KPI_COLUMNS,
        "operating_margin_ttm",
        "current_ratio",
        "cash_to_assets",
        *FORECAST_COLUMNS,
    ]
    result = (
        features[columns]
        .merge(identity, on="cik", how="left")
        .merge(pred, on="decision_key", how="left")
    )
    result["prediction_status"] = result["evaluation_sample"].fillna(
        "Not scored (training/history)"
    )
    result["risk_band"] = _risk_band(result["probability"])
    return result.sort_values(["company_name", "decision_at"])


def _model_performance(root: Path, champion: dict[str, Any]) -> pd.DataFrame:
    reports = root / "reports" / "generated"
    development = pd.read_csv(reports / "classifier_fold_metrics.csv")
    development["evaluation_sample"] = "OOF development backtest"
    holdout = pd.read_csv(reports / "final_holdout_metrics.csv")
    holdout["fold_id"] = "final_holdout"
    holdout["model"] = champion["model"]
    holdout["feature_increment"] = champion["feature_increment"]
    holdout["evaluation_sample"] = "Locked final holdout"
    result = pd.concat([development, holdout], ignore_index=True, sort=False)
    result["is_champion"] = result["model"].eq(champion["model"]) & result["feature_increment"].eq(
        champion["feature_increment"]
    )
    result["metric_scope_note"] = np.where(
        result["evaluation_sample"].eq("OOF development backtest"),
        "Out-of-fold only",
        "One-time untouched holdout evaluation",
    )
    return result


def _reconcile(
    overview: pd.DataFrame,
    watchlist: pd.DataFrame,
    history: pd.DataFrame,
    performance: pd.DataFrame,
) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, evidence: Any) -> None:
        checks.append({"check": name, "passed": bool(passed), "evidence": str(evidence)})

    add(
        "watchlist_unique_decision_company",
        not watchlist.duplicated(["decision_at", "cik"]).any(),
        len(watchlist),
    )
    add(
        "history_unique_company_fiscal_period",
        not history["decision_key"].duplicated().any(),
        len(history),
    )
    add(
        "overview_unique_snapshot_sector",
        not overview.duplicated(["snapshot_as_of", "sector"]).any(),
        len(overview),
    )
    add(
        "watchlist_probabilities_bounded",
        bool(watchlist["probability"].between(0, 1).all()),
        watchlist["probability"].min(),
    )
    add(
        "backtests_are_oof",
        bool(
            performance.loc[
                performance["evaluation_sample"].str.contains("development"),
                "metric_scope_note",
            ]
            .eq("Out-of-fold only")
            .all()
        ),
        "OOF-only development metrics",
    )
    add("company_count_reconciles", watchlist["cik"].nunique() == 60, watchlist["cik"].nunique())
    add(
        "overview_alerts_reconcile",
        int(overview["alerts"].sum()) == int(watchlist["alert"].sum()),
        int(watchlist["alert"].sum()),
    )
    for column in KPI_COLUMNS:
        source = history.set_index("decision_key")[column]
        sample = watchlist.set_index("decision_key")[column]
        equal = np.allclose(source.loc[sample.index], sample, equal_nan=True)
        add(f"{column}_reconciles", equal, len(sample))
    frame = pd.DataFrame(checks)
    if not frame["passed"].all():
        raise ValueError(
            f"Stage 17 reconciliation failed: {frame.loc[~frame['passed']].to_dict('records')}"
        )
    return frame


def run_stage_17() -> dict[str, Any]:
    root = repository_root()
    export_directory = root / "dashboards" / "powerbi" / "exports"
    reports = root / "reports" / "generated"
    export_directory.mkdir(parents=True, exist_ok=True)
    features = pd.read_parquet(
        root / "data" / "processed" / "model_features_with_forecasts.parquet"
    )
    predictions, champion = _champion_predictions(root)
    watchlist = _watchlist(features, predictions)
    overview = _portfolio_overview(watchlist)
    history = _company_history(features, predictions)
    performance = _model_performance(root, champion)
    outputs = {
        "portfolio_overview": overview,
        "company_watchlist": watchlist,
        "company_detail_history": history,
        "model_performance": performance,
    }
    for name, frame in outputs.items():
        frame.to_csv(export_directory / f"{name}.csv", index=False, date_format="%Y-%m-%d")
    reconciliation = _reconcile(overview, watchlist, history, performance)
    reconciliation.to_csv(reports / "powerbi_reconciliation.csv", index=False)
    result = {
        "status": "complete",
        "stage": 17,
        "export_format": "CSV",
        "public_data_only": True,
        "outputs": {name: len(frame) for name, frame in outputs.items()},
        "companies": int(watchlist["cik"].nunique()),
        "reconciliation_checks_passed": int(reconciliation["passed"].sum()),
        "backtest_policy": "OOF development predictions only; holdout labeled separately",
        "powerbi_import_workbook": (
            "outputs/powerbi_stage17/"
            "Corporate_Financial_Deterioration_PowerBI_Import.xlsx"
        ),
        "powerbi_report": (
            "dashboards/powerbi/deliverables/Corporate_Financial_Deterioration.pbix"
        ),
        "dashboard_pages": [
            "Portfolio Overview",
            "Analyst Watchlist",
            "Company Detail",
            "Model Performance",
        ],
    }
    (reports / "stage17_summary.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
