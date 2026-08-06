"""Rolling-origin KPI forecast evaluation and leakage-safe forecast features."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from cfd.forecasting.models import forecast_series
from cfd.panel import KPI_COLUMNS


def build_forecast_backtest(
    panel: pd.DataFrame,
    fold_summary: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """Forecast from the last issuer observation preceding each validation window."""

    rows: list[dict[str, Any]] = []
    models = list(config["candidate_models"])
    horizons = [int(value) for value in config["horizons"]]
    maximum_horizon = max(horizons)
    minimum_history = int(config["minimum_history"])
    exog_columns = list(config["regression_exog"])
    ordered = panel.sort_values(["cik", "decision_at"])
    for fold in fold_summary.itertuples(index=False):
        validation_start = pd.to_datetime(str(fold.validation_start))
        for cik, company in ordered.groupby("cik", sort=True):
            company = company.sort_values("decision_at").reset_index(drop=True)
            earlier = company.index[company["decision_at"] < validation_start]
            if earlier.empty:
                continue
            origin_position = int(earlier.max())
            origin = company.iloc[origin_position]
            for kpi in KPI_COLUMNS:
                history_frame = company.iloc[: origin_position + 1]
                history = history_frame[kpi]
                if history.notna().sum() < minimum_history:
                    continue
                for model_name in models:
                    forecast_result = forecast_series(
                        history,
                        model_name=model_name,
                        horizon=maximum_horizon,
                        exog_history=history_frame[exog_columns],
                        maxiter=int(config["state_space_maxiter"]),
                    )
                    for horizon in horizons:
                        target_position = origin_position + horizon
                        if target_position >= len(company):
                            continue
                        target = company.iloc[target_position]
                        origin_fiscal_position = int(origin["fiscal_year"]) * 4 + int(
                            origin["fiscal_quarter_number"]
                        )
                        target_fiscal_position = int(target["fiscal_year"]) * 4 + int(
                            target["fiscal_quarter_number"]
                        )
                        if target_fiscal_position - origin_fiscal_position != horizon:
                            continue
                        actual = target[kpi]
                        if pd.isna(actual):
                            continue
                        forecast = float(forecast_result.mean[horizon - 1])
                        lower = float(forecast_result.lower[horizon - 1])
                        upper = float(forecast_result.upper[horizon - 1])
                        rows.append(
                            {
                                "fold_id": str(fold.fold_id),
                                "cik": str(cik),
                                "sector": str(origin["sector"]),
                                "origin_decision_key": str(origin["decision_key"]),
                                "origin_at": origin["decision_at"],
                                "target_at": target["decision_at"],
                                "kpi": kpi,
                                "model": model_name,
                                "horizon": horizon,
                                "actual": float(actual),
                                "forecast": forecast,
                                "lower": lower,
                                "upper": upper,
                                "error": forecast - float(actual),
                                "absolute_error": abs(forecast - float(actual)),
                                "squared_error": (forecast - float(actual)) ** 2,
                                "interval_covered": lower <= float(actual) <= upper,
                                "converged": forecast_result.converged,
                                "fallback_used": forecast_result.fallback_used,
                            }
                        )
    output = pd.DataFrame(rows)
    if output.empty:
        raise ValueError("Forecast backtest produced no evaluable predictions")
    return output


def summarize_forecasts(predictions: pd.DataFrame) -> pd.DataFrame:
    grouped = predictions.groupby(["kpi", "horizon", "model"], as_index=False)
    metrics = grouped.agg(
        observations=("actual", "size"),
        MAE=("absolute_error", "mean"),
        RMSE=("squared_error", lambda values: float(np.sqrt(values.mean()))),
        interval_coverage=("interval_covered", "mean"),
        convergence_rate=("converged", "mean"),
        fallback_rate=("fallback_used", "mean"),
    )
    sector_rmse = (
        predictions.groupby(["kpi", "horizon", "model", "sector"])["squared_error"]
        .mean()
        .pow(0.5)
        .groupby(["kpi", "horizon", "model"])
        .agg(sector_rmse_mean="mean", sector_rmse_std="std")
        .reset_index()
    )
    return metrics.merge(sector_rmse, on=["kpi", "horizon", "model"], how="left")


def select_forecast_champions(metrics: pd.DataFrame) -> pd.DataFrame:
    ranked = metrics.sort_values(
        ["kpi", "horizon", "RMSE", "MAE", "sector_rmse_std", "model"],
        na_position="last",
    ).copy()
    ranked["rank"] = ranked.groupby(["kpi", "horizon"]).cumcount() + 1
    ranked["selected"] = ranked["rank"].eq(1)
    return ranked


def generate_forecast_features(
    panel: pd.DataFrame,
    champions: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """Generate prespecified four-quarter features using only prior/current history.

    Forecast champions are accepted to enforce that Stage 13 selection has completed, but model
    family performance from later folds is deliberately not used to construct classifier inputs.
    """

    if champions.loc[champions["selected"]].empty:
        raise ValueError("Forecast selection evidence is required before feature generation")
    feature_model = str(config["classifier_feature_model"])
    minimum_history = int(config["minimum_history"])
    exog_columns = list(config["regression_exog"])
    rows: list[dict[str, Any]] = []
    for _cik, company in panel.sort_values(["cik", "decision_at"]).groupby("cik", sort=True):
        company = company.sort_values("decision_at").reset_index(drop=True)
        for position, (_, current) in enumerate(company.iterrows()):
            row: dict[str, Any] = {
                "decision_key": current["decision_key"],
                "forecast_feature_available_at": current["decision_at"],
            }
            history_frame = company.iloc[: position + 1]
            for kpi in KPI_COLUMNS:
                stem = kpi.removesuffix("_ttm")
                history = history_frame[kpi]
                if history.notna().sum() < minimum_history:
                    row[f"forecast_{stem}_4q"] = np.nan
                    row[f"forecast_{stem}_change_4q"] = np.nan
                    row[f"forecast_{stem}_uncertainty_4q"] = np.nan
                    continue
                result = forecast_series(
                    history,
                    model_name=feature_model,
                    horizon=4,
                    exog_history=history_frame[exog_columns],
                    maxiter=int(config["state_space_maxiter"]),
                )
                forecast = float(result.mean[3])
                current_value = history.dropna().iloc[-1]
                row[f"forecast_{stem}_4q"] = forecast
                row[f"forecast_{stem}_change_4q"] = forecast - float(current_value)
                row[f"forecast_{stem}_uncertainty_4q"] = float(result.upper[3] - result.lower[3])
            rows.append(row)
    return pd.DataFrame(rows)
