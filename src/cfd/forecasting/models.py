"""Constrained forecasting models and uncertainty intervals for Phase 1."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from statsmodels.tsa.statespace.structural import (  # type: ignore[import-untyped]
    UnobservedComponents,
)

from cfd.forecasting.baselines import random_walk_forecast, random_walk_with_drift_forecast


@dataclass(frozen=True)
class ForecastResult:
    mean: NDArray[np.float64]
    lower: NDArray[np.float64]
    upper: NDArray[np.float64]
    converged: bool
    fallback_used: bool


def _baseline_interval(history: pd.Series, mean: NDArray[np.float64]) -> ForecastResult:
    clean = history.dropna().astype(float)
    differences = clean.diff().dropna()
    scale = float(differences.std(ddof=1)) if len(differences) > 1 else 0.0
    steps = np.sqrt(np.arange(1, len(mean) + 1, dtype=float))
    width = 1.96 * max(scale, np.finfo(float).eps) * steps
    return ForecastResult(mean, mean - width, mean + width, True, False)


def forecast_series(
    history: pd.Series,
    *,
    model_name: str,
    horizon: int,
    exog_history: pd.DataFrame | None = None,
    maxiter: int = 100,
) -> ForecastResult:
    """Fit one candidate using only the supplied history and safely fall back if needed."""

    clean = history.astype(float).replace([np.inf, -np.inf], np.nan)
    valid = clean.notna()
    clean = clean.loc[valid]
    if len(clean) < 2 or horizon < 1:
        raise ValueError("Forecasting requires at least two observations and a positive horizon")
    if model_name == "random_walk":
        return _baseline_interval(clean, random_walk_forecast(clean, horizon))
    if model_name == "random_walk_drift":
        return _baseline_interval(clean, random_walk_with_drift_forecast(clean, horizon))

    try:
        exog: pd.DataFrame | None = None
        future_exog: pd.DataFrame | None = None
        if model_name == "regression_dlm":
            if exog_history is None:
                raise ValueError("Regression DLM requires exogenous history")
            exog = exog_history.loc[valid].astype(float).ffill().bfill()
            varying = exog.columns[exog.nunique(dropna=True) > 1]
            exog = exog[list(varying)]
            if exog.empty or exog.isna().any().any():
                raise ValueError("Regression DLM exogenous inputs are unusable")
            future_exog = pd.DataFrame(
                np.repeat(exog.iloc[[-1]].to_numpy(), horizon, axis=0), columns=exog.columns
            )
            specification: dict[str, Any] = {
                "level": "local linear trend",
                "exog": exog.to_numpy(),
            }
        elif model_name == "local_level":
            specification = {"level": "local level"}
        elif model_name == "local_linear_trend":
            specification = {"level": "local linear trend"}
        else:
            raise ValueError(f"Unknown forecasting model: {model_name}")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = UnobservedComponents(clean.to_numpy(), **specification)
            fitted = model.fit(disp=False, maxiter=maxiter)
            prediction = fitted.get_forecast(
                steps=horizon,
                exog=None if future_exog is None else future_exog.to_numpy(),
            )
        mean = np.asarray(prediction.predicted_mean, dtype=float)
        interval = np.asarray(prediction.conf_int(alpha=0.05), dtype=float)
        converged = bool(fitted.mle_retvals.get("converged", True))
        if not converged:
            raise ValueError("State-space optimizer did not converge")
        if not np.isfinite(mean).all() or not np.isfinite(interval).all():
            raise ValueError("Nonfinite state-space forecast")
        return ForecastResult(mean, interval[:, 0], interval[:, 1], converged, False)
    except (ValueError, TypeError, np.linalg.LinAlgError):
        fallback = _baseline_interval(clean, random_walk_forecast(clean, horizon))
        return ForecastResult(fallback.mean, fallback.lower, fallback.upper, False, True)
