"""Leakage-safe historical feature engineering and fold-local preprocessing."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin  # type: ignore[import-untyped]
from sklearn.compose import ColumnTransformer  # type: ignore[import-untyped]
from sklearn.impute import SimpleImputer  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # type: ignore[import-untyped]

from cfd.panel import KPI_COLUMNS


class TrainingQuantileClipper(TransformerMixin, BaseEstimator):  # type: ignore[misc]
    """Clip with quantiles learned exclusively from the fitted training rows."""

    def __init__(self, lower: float = 0.01, upper: float = 0.99) -> None:
        self.lower = lower
        self.upper = upper

    def fit(self, x: Any, y: Any = None) -> TrainingQuantileClipper:
        values = np.asarray(x, dtype=float)
        self.n_features_in_ = values.shape[1]
        self.lower_bounds_ = np.nanquantile(values, self.lower, axis=0)
        self.upper_bounds_ = np.nanquantile(values, self.upper, axis=0)
        return self

    def transform(self, x: Any) -> np.ndarray[Any, np.dtype[np.float64]]:
        values = np.asarray(x, dtype=float)
        return np.clip(values, self.lower_bounds_, self.upper_bounds_)

    def get_feature_names_out(self, input_features: Any = None) -> np.ndarray[Any, Any]:
        if input_features is None:
            input_features = [f"x{index}" for index in range(self.n_features_in_)]
        return np.asarray(input_features, dtype=object)


def _rolling_slope(values: pd.Series) -> float:
    clean = values.dropna().astype(float)
    if len(clean) < 3:
        return np.nan
    x = np.arange(len(clean), dtype=float)
    return float(np.polyfit(x, clean.to_numpy(), 1)[0])


def engineer_historical_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Create only contemporaneous and backward-looking features."""

    result = panel.sort_values(["cik", "decision_at"]).copy()
    grouped = result.groupby("cik", sort=False)
    for kpi in KPI_COLUMNS:
        result[f"{kpi}_lag1"] = grouped[kpi].shift(1)
        result[f"{kpi}_lag2"] = grouped[kpi].shift(2)
        result[f"{kpi}_lag4"] = grouped[kpi].shift(4)
        result[f"{kpi}_yoy_change"] = result[kpi] - result[f"{kpi}_lag4"]
        result[f"{kpi}_volatility_4q"] = (
            grouped[kpi].rolling(4, min_periods=3).std().reset_index(level=0, drop=True)
        )
        result[f"{kpi}_trend_4q"] = (
            grouped[kpi]
            .rolling(4, min_periods=3)
            .apply(_rolling_slope, raw=False)
            .reset_index(level=0, drop=True)
        )
    for macro in ["INDPRO", "RSAFS"]:
        result[f"{macro}_yoy_change"] = grouped[macro].pct_change(4, fill_method=None)
    result["utility_x_leverage"] = (
        result["sector"].eq("Utilities").astype(int) * result["total_debt_to_assets"]
    )
    result["discretionary_x_retail_sales_yoy"] = (
        result["sector"].eq("Consumer Discretionary").astype(int) * result["RSAFS_yoy_change"]
    )
    result["feature_available_at"] = result[
        ["maximum_source_available_at", "macro_available_at_max"]
    ].max(axis=1)
    missing_indicators = {
        f"{column}_missing": result[column].isna()
        for column in result.select_dtypes(include=["number"]).columns
        if column != "deterioration_label"
        and not column.endswith("_missing")
        and f"{column}_missing" not in result.columns
    }
    result = pd.concat([result, pd.DataFrame(missing_indicators, index=result.index)], axis=1)
    if (result["feature_available_at"] > result["decision_at"]).any():
        raise ValueError("Engineered feature uses information unavailable at decision time")
    if result["decision_key"].duplicated().any():
        raise ValueError("Feature output contains duplicate decision keys")
    return result.sort_values(["decision_at", "cik"]).reset_index(drop=True)


def build_fold_preprocessor(
    *,
    numeric_features: list[str],
    categorical_features: list[str],
    scale_numeric: bool,
) -> ColumnTransformer:
    """Return an unfitted transformer that must be fit on one temporal training fold."""

    numeric_steps: list[tuple[str, Any]] = [
        ("clip", TrainingQuantileClipper()),
        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
    ]
    if scale_numeric:
        numeric_steps.append(("scale", StandardScaler()))
    numeric_pipeline = Pipeline(numeric_steps)
    categorical_pipeline = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("one_hot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        [
            ("numeric", numeric_pipeline, numeric_features),
            ("categorical", categorical_pipeline, categorical_features),
        ],
        remainder="drop",
    )
