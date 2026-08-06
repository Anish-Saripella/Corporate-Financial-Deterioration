"""Probability calibration methods fitted only on development predictions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.optimize import minimize_scalar  # type: ignore[import-untyped]
from sklearn.isotonic import IsotonicRegression  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]


def _validate(probabilities: NDArray[Any]) -> NDArray[np.float64]:
    values = np.asarray(probabilities, dtype=float)
    if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
        raise ValueError("Probabilities must be finite and between zero and one")
    return np.asarray(np.clip(values, 1e-6, 1 - 1e-6), dtype=float)


def _logit(probabilities: NDArray[Any]) -> NDArray[np.float64]:
    values = _validate(probabilities)
    return np.asarray(np.log(values / (1 - values)), dtype=float)


@dataclass
class ProbabilityCalibrator:
    """Small common wrapper for none, intercept, Platt, and isotonic scaling."""

    method: str
    fitted_model: Any = None

    def fit(
        self, probabilities: NDArray[Any], labels: NDArray[Any]
    ) -> ProbabilityCalibrator:
        scores = _validate(probabilities)
        target = np.asarray(labels, dtype=int)
        if len(scores) != len(target) or np.unique(target).size < 2:
            raise ValueError("Calibration requires aligned predictions with both label classes")
        if self.method == "none":
            self.fitted_model = True
        elif self.method == "intercept":
            logits = _logit(scores)

            def loss(intercept: float) -> float:
                adjusted = 1 / (1 + np.exp(-(logits + intercept)))
                return float(
                    -np.mean(target * np.log(adjusted) + (1 - target) * np.log(1 - adjusted))
                )

            self.fitted_model = float(minimize_scalar(loss, bounds=(-10, 10), method="bounded").x)
        elif self.method == "platt":
            model = LogisticRegression(C=1e6, max_iter=1000)
            model.fit(_logit(scores).reshape(-1, 1), target)
            self.fitted_model = model
        elif self.method == "isotonic":
            model = IsotonicRegression(out_of_bounds="clip")
            model.fit(scores, target)
            self.fitted_model = model
        else:
            raise ValueError(f"Unknown calibration method: {self.method}")
        return self

    def predict(self, probabilities: NDArray[Any]) -> NDArray[np.float64]:
        if self.fitted_model is None:
            raise ValueError("Calibrator must be fitted before prediction")
        scores = _validate(probabilities)
        if self.method == "none":
            return scores
        if self.method == "intercept":
            return np.asarray(1 / (1 + np.exp(-(_logit(scores) + self.fitted_model))), dtype=float)
        if self.method == "platt":
            return np.asarray(
                self.fitted_model.predict_proba(_logit(scores).reshape(-1, 1))[:, 1], dtype=float
            )
        return np.asarray(self.fitted_model.predict(scores), dtype=float)


def cross_fitted_temporal_calibration(
    predictions: pd.DataFrame,
    methods: list[str],
    *,
    sector_specific: bool = False,
) -> pd.DataFrame:
    """Calibrate each fold using only predictions from earlier validation folds.

    The first fold has no earlier out-of-fold evidence and is therefore omitted.
    This is preferable to fitting and evaluating a calibrator on the same rows.
    """

    required = {"decision_at", "fold_id", "sector", "deterioration_label", "probability"}
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"Calibration predictions are missing columns: {sorted(missing)}")
    data = predictions.copy()
    data["decision_at"] = pd.to_datetime(data["decision_at"])
    fold_order = (
        data.groupby("fold_id")["decision_at"].min().sort_values().index.tolist()
    )
    output: list[pd.DataFrame] = []
    for fold_position, fold_id in enumerate(fold_order):
        if fold_position == 0:
            continue
        previous_folds = fold_order[:fold_position]
        calibration_pool = data.loc[data["fold_id"].isin(previous_folds)]
        validation = data.loc[data["fold_id"] == fold_id]
        group_columns = ["sector"] if sector_specific else []
        calibration_groups = (
            calibration_pool.groupby(group_columns, sort=True)
            if group_columns
            else [("Overall", calibration_pool)]
        )
        for group_name, fit_rows in calibration_groups:
            score_rows = (
                validation.loc[validation["sector"] == group_name]
                if sector_specific
                else validation
            )
            if score_rows.empty or fit_rows["deterioration_label"].nunique() < 2:
                continue
            for method in methods:
                calibrator = ProbabilityCalibrator(method).fit(
                    fit_rows["probability"].to_numpy(dtype=float),
                    fit_rows["deterioration_label"].to_numpy(dtype=int),
                )
                calibrated = score_rows.copy()
                calibrated["raw_probability"] = calibrated["probability"]
                calibrated["probability"] = calibrator.predict(
                    calibrated["raw_probability"].to_numpy(dtype=float)
                )
                calibrated["calibration_method"] = method
                calibrated["calibration_scope"] = (
                    str(group_name) if sector_specific else "pooled"
                )
                calibrated["calibration_training_folds"] = len(previous_folds)
                output.append(calibrated)
    if not output:
        return pd.DataFrame()
    return pd.concat(output, ignore_index=True)
