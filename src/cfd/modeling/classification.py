"""Time-aware deterioration classification, calibration, and evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.metrics import (  # type: ignore[import-untyped]
    average_precision_score,
    brier_score_loss,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from xgboost import XGBClassifier

from cfd.features.engineering import build_fold_preprocessor


@dataclass
class ClassifierBundle:
    estimator: Pipeline
    calibrator: LogisticRegression | None
    threshold: float
    numeric_features: list[str]
    categorical_features: list[str]
    model_name: str
    feature_increment: str

    def predict_probability(self, frame: pd.DataFrame) -> NDArray[np.float64]:
        raw = np.asarray(self.estimator.predict_proba(frame)[:, 1], dtype=float)
        if self.calibrator is None:
            return raw
        logits = _logit(raw).reshape(-1, 1)
        return np.asarray(self.calibrator.predict_proba(logits)[:, 1], dtype=float)


def _logit(probabilities: NDArray[np.float64]) -> NDArray[np.float64]:
    clipped = np.clip(probabilities, 1e-6, 1 - 1e-6)
    return np.asarray(np.log(clipped / (1 - clipped)), dtype=float)


def _feature_sets(
    registry: dict[str, Any], classification_config: dict[str, Any]
) -> dict[str, tuple[list[str], list[str]]]:
    numeric = list(registry["numeric_features"])
    categorical = list(registry["categorical_features"])
    macro = {
        "DFF",
        "T10Y2Y",
        "BAA10Y",
        "UNRATE",
        "INDPRO_yoy_change",
        "RSAFS_yoy_change",
        "utility_x_leverage",
        "discretionary_x_retail_sales_yoy",
    }
    current_spec = classification_config["feature_increments"]["current_fundamentals"]
    current_numeric = [value for value in current_spec if value not in categorical]
    historical = [value for value in numeric if value not in macro]
    interest_forecasts = [
        "forecast_interest_coverage_4q",
        "forecast_interest_coverage_change_4q",
        "forecast_interest_coverage_uncertainty_4q",
    ]
    all_forecasts = [
        *interest_forecasts,
        "forecast_free_cash_flow_margin_4q",
        "forecast_free_cash_flow_margin_change_4q",
        "forecast_free_cash_flow_margin_uncertainty_4q",
        "forecast_total_debt_to_assets_4q",
        "forecast_total_debt_to_assets_change_4q",
        "forecast_total_debt_to_assets_uncertainty_4q",
    ]
    return {
        "current_fundamentals": (current_numeric, categorical),
        "historical_and_peer": (historical, categorical),
        "forecast_interest_coverage": ([*historical, *interest_forecasts], categorical),
        "all_forecasts": ([*historical, *all_forecasts], categorical),
        "macro_and_interactions": ([*numeric, *all_forecasts], categorical),
    }


def _make_estimator(
    model_name: str,
    numeric_features: list[str],
    categorical_features: list[str],
    config: dict[str, Any],
) -> Pipeline:
    preprocessor = build_fold_preprocessor(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        scale_numeric=model_name == "logistic_regression",
    )
    if model_name == "logistic_regression":
        model: Any = LogisticRegression(
            C=float(config["logistic_c"]),
            class_weight="balanced",
            max_iter=2000,
            random_state=20260802,
        )
    elif model_name == "gradient_boosted_trees":
        specification = config["xgboost"]
        model = XGBClassifier(
            **specification,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=20260802,
            n_jobs=4,
        )
    else:
        raise ValueError(f"Unknown classifier: {model_name}")
    return Pipeline([("preprocess", preprocessor), ("model", model)])


def _calibration_split(
    training: pd.DataFrame, calibration_quarters: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    last_period = training["decision_at"].max().to_period("Q")
    calibration_start = (last_period - calibration_quarters + 1).start_time
    fit = training.loc[training["decision_at"] < calibration_start]
    calibration = training.loc[training["decision_at"] >= calibration_start]
    if fit["deterioration_label"].nunique() < 2 or calibration["deterioration_label"].nunique() < 2:
        ordered_periods = sorted(training["decision_at"].dt.to_period("Q").unique())
        split = max(int(len(ordered_periods) * 0.8), 1)
        calibration_start = ordered_periods[min(split, len(ordered_periods) - 1)].start_time
        fit = training.loc[training["decision_at"] < calibration_start]
        calibration = training.loc[training["decision_at"] >= calibration_start]
    if fit.empty or fit["deterioration_label"].nunique() < 2:
        raise ValueError("Training history cannot support an internal calibration split")
    return fit, calibration


def _select_threshold(
    y_true: NDArray[Any], probabilities: NDArray[np.float64], maximum_alert_rate: float
) -> float:
    candidates = np.unique(np.quantile(probabilities, np.linspace(0.5, 0.95, 19)))
    best = (float("-inf"), 0.5)
    for threshold in candidates:
        predictions = probabilities >= threshold
        if predictions.mean() > maximum_alert_rate or predictions.sum() == 0:
            continue
        precision = precision_score(y_true, predictions, zero_division=0)
        recall = recall_score(y_true, predictions, zero_division=0)
        f2 = 5 * precision * recall / max(4 * precision + recall, np.finfo(float).eps)
        if f2 > best[0]:
            best = (float(f2), float(threshold))
    return best[1]


def fit_classifier_bundle(
    training: pd.DataFrame,
    *,
    model_name: str,
    feature_increment: str,
    numeric_features: list[str],
    categorical_features: list[str],
    config: dict[str, Any],
) -> ClassifierBundle:
    fit, calibration = _calibration_split(training, int(config["calibration_quarters"]))
    estimator = _make_estimator(model_name, numeric_features, categorical_features, config)
    columns = [*numeric_features, *categorical_features]
    estimator.fit(fit[columns], fit["deterioration_label"].astype(int))
    raw = np.asarray(estimator.predict_proba(calibration[columns])[:, 1], dtype=float)
    y_calibration = calibration["deterioration_label"].astype(int).to_numpy()
    calibrator: LogisticRegression | None = None
    calibrated = raw
    if len(np.unique(y_calibration)) == 2:
        calibrator = LogisticRegression(C=1e6, max_iter=1000)
        calibrator.fit(_logit(raw).reshape(-1, 1), y_calibration)
        calibrated = np.asarray(
            calibrator.predict_proba(_logit(raw).reshape(-1, 1))[:, 1], dtype=float
        )
    threshold = _select_threshold(y_calibration, calibrated, float(config["maximum_alert_rate"]))
    return ClassifierBundle(
        estimator,
        calibrator,
        threshold,
        numeric_features,
        categorical_features,
        model_name,
        feature_increment,
    )


def expected_calibration_error(
    y_true: NDArray[Any], probabilities: NDArray[np.float64], bins: int = 10
) -> float:
    boundaries = np.linspace(0, 1, bins + 1)
    error = 0.0
    for lower, upper in pairwise(boundaries):
        selected = (probabilities >= lower) & (
            probabilities <= upper if upper == 1 else probabilities < upper
        )
        if selected.any():
            error += selected.mean() * abs(y_true[selected].mean() - probabilities[selected].mean())
    return float(error)


def classification_metrics(
    y_true: NDArray[Any], probabilities: NDArray[np.float64], threshold: float
) -> dict[str, float]:
    predicted = probabilities >= threshold
    prevalence = max(float(y_true.mean()), np.finfo(float).eps)
    top_count = max(int(np.ceil(len(y_true) * 0.10)), 1)
    top_indices = np.argsort(probabilities)[-top_count:]
    return {
        "PR_AUC": float(average_precision_score(y_true, probabilities)),
        "recall": float(recall_score(y_true, predicted, zero_division=0)),
        "precision": float(precision_score(y_true, predicted, zero_division=0)),
        "top_decile_lift": float(y_true[top_indices].mean() / prevalence),
        "Brier_score": float(brier_score_loss(y_true, probabilities)),
        "calibration_error": expected_calibration_error(y_true, probabilities),
        "alert_rate": float(predicted.mean()),
        "false_alert_rate": float(((predicted) & (y_true == 0)).sum() / max(predicted.sum(), 1)),
    }


def run_temporal_classification(
    features: pd.DataFrame,
    assignments: pd.DataFrame,
    registry: dict[str, Any],
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_sets = _feature_sets(registry, config)
    rows: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    indexed = features.set_index("decision_key", drop=False)
    for fold_id in sorted(assignments["fold_id"].unique()):
        fold = assignments.loc[assignments["fold_id"] == fold_id]
        train_keys = fold.loc[fold["split"] == "TRAIN", "decision_key"]
        validation_keys = fold.loc[fold["split"] == "VALIDATION", "decision_key"]
        training = indexed.loc[train_keys].dropna(subset=["deterioration_label"]).copy()
        validation = indexed.loc[validation_keys].dropna(subset=["deterioration_label"]).copy()
        for increment, (numeric, categorical) in feature_sets.items():
            columns = [*numeric, *categorical]
            for model_name in config["candidate_models"]:
                bundle = fit_classifier_bundle(
                    training,
                    model_name=model_name,
                    feature_increment=increment,
                    numeric_features=numeric,
                    categorical_features=categorical,
                    config=config,
                )
                probabilities = bundle.predict_probability(validation[columns])
                y_true = validation["deterioration_label"].astype(int).to_numpy()
                output = validation[
                    ["decision_key", "cik", "decision_at", "sector", "deterioration_label"]
                ].copy()
                output["fold_id"] = fold_id
                output["model"] = model_name
                output["feature_increment"] = increment
                output["probability"] = probabilities
                output["threshold"] = bundle.threshold
                output["alert"] = probabilities >= bundle.threshold
                rows.append(output)
                metric_rows.append(
                    {
                        "fold_id": fold_id,
                        "sector": "Overall",
                        "model": model_name,
                        "feature_increment": increment,
                        "observations": len(validation),
                        **classification_metrics(y_true, probabilities, bundle.threshold),
                    }
                )
                for sector, sector_rows in output.groupby("sector"):
                    sector_y = sector_rows["deterioration_label"].astype(int).to_numpy()
                    sector_p = sector_rows["probability"].to_numpy(dtype=float)
                    metric_rows.append(
                        {
                            "fold_id": fold_id,
                            "sector": sector,
                            "model": model_name,
                            "feature_increment": increment,
                            "observations": len(sector_rows),
                            **classification_metrics(sector_y, sector_p, bundle.threshold),
                        }
                    )
    return pd.concat(rows, ignore_index=True), pd.DataFrame(metric_rows)


def available_feature_sets(
    registry: dict[str, Any], config: dict[str, Any]
) -> dict[str, tuple[list[str], list[str]]]:
    return _feature_sets(registry, config)
