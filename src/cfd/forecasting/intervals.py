"""Empirical forecast-interval recalibration for Phase 2."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class IntervalCalibration:
    kpi: str
    sector: str
    horizon: int
    absolute_residual_quantile: float
    calibration_observations: int
    interval_level: float


def fit_empirical_intervals(
    calibration_forecasts: pd.DataFrame,
    *,
    interval_level: float = 0.95,
    minimum_group_observations: int = 30,
) -> pd.DataFrame:
    """Learn symmetric residual widths from completed development forecasts.

    A sector-specific width is used only when it has enough observations;
    otherwise it falls back to the corresponding pooled KPI/horizon width.
    No distributional normality assumption is required.
    """

    required = {"kpi", "sector", "horizon", "actual", "forecast"}
    missing = required - set(calibration_forecasts.columns)
    if missing:
        raise ValueError(f"Forecast calibration is missing columns: {sorted(missing)}")
    if not 0 < interval_level < 1:
        raise ValueError("interval_level must be between zero and one")
    data = calibration_forecasts.dropna(subset=["actual", "forecast"]).copy()
    data["absolute_residual"] = (data["actual"] - data["forecast"]).abs()
    pooled = (
        data.groupby(["kpi", "horizon"])["absolute_residual"]
        .agg(
            pooled_width=lambda values: values.quantile(interval_level),
            pooled_observations="size",
        )
        .reset_index()
    )
    sector = (
        data.groupby(["kpi", "sector", "horizon"])["absolute_residual"]
        .agg(
            sector_width=lambda values: values.quantile(interval_level),
            sector_observations="size",
        )
        .reset_index()
        .merge(pooled, on=["kpi", "horizon"], validate="many_to_one")
    )
    sector["absolute_residual_quantile"] = np.where(
        sector["sector_observations"] >= minimum_group_observations,
        sector["sector_width"],
        sector["pooled_width"],
    )
    sector["calibration_observations"] = np.where(
        sector["sector_observations"] >= minimum_group_observations,
        sector["sector_observations"],
        sector["pooled_observations"],
    )
    sector["calibration_scope"] = np.where(
        sector["sector_observations"] >= minimum_group_observations,
        "sector_kpi_horizon",
        "pooled_kpi_horizon_fallback",
    )
    sector["interval_level"] = interval_level
    return sector[
        [
            "kpi",
            "sector",
            "horizon",
            "absolute_residual_quantile",
            "calibration_observations",
            "calibration_scope",
            "interval_level",
        ]
    ]


def apply_empirical_intervals(forecasts: pd.DataFrame, calibration: pd.DataFrame) -> pd.DataFrame:
    """Apply frozen development residual widths to later forecasts."""

    result = forecasts.merge(
        calibration,
        on=["kpi", "sector", "horizon"],
        how="left",
        validate="many_to_one",
    )
    if result["absolute_residual_quantile"].isna().any():
        missing = result.loc[
            result["absolute_residual_quantile"].isna(),
            [
                "kpi",
                "sector",
                "horizon",
            ],
        ].drop_duplicates()
        raise ValueError(f"No empirical interval calibration for: {missing.to_dict('records')}")
    result["lower_interval"] = result["forecast"] - result["absolute_residual_quantile"]
    result["upper_interval"] = result["forecast"] + result["absolute_residual_quantile"]
    if "actual" in result:
        result["interval_covered"] = result["actual"].between(
            result["lower_interval"], result["upper_interval"], inclusive="both"
        )
    return result
