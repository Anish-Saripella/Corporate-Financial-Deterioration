"""Nested temporal logistic challengers for the Phase 2 panel."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.metrics import average_precision_score  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from xgboost import XGBClassifier

from cfd.features.engineering import build_fold_preprocessor


def _equal_sector_sample_weight(training: pd.DataFrame) -> np.ndarray[Any, np.dtype[np.float64]]:
    """Give each sector equal total training weight despite unequal issuer counts."""

    counts = training["sector"].value_counts()
    weights = training["sector"].map(lambda sector: 1.0 / float(counts[sector])).to_numpy()
    return np.asarray(weights / weights.mean(), dtype=float)


@dataclass
class NestedSelection:
    regularization_c: float
    positive_class_weight: float
    mean_inner_pr_auc: float
    inner_folds: int


@dataclass
class BoostingSelection:
    parameters: dict[str, Any]
    mean_inner_pr_auc: float
    inner_folds: int


def add_prespecified_sector_interactions(
    frame: pd.DataFrame, features: list[str]
) -> tuple[pd.DataFrame, list[str]]:
    """Add Utility coefficient deviations while preserving a shared base effect.

    L2 regularization shrinks deviations toward zero, so both sectors share
    information unless development data consistently support a difference.
    """

    result = frame.copy()
    utility = result["sector"].eq("Utilities").astype(float)
    interaction_names = []
    for feature in features:
        if feature not in result:
            raise ValueError(f"Sector interaction feature is absent: {feature}")
        name = f"utility_x_{feature}"
        result[name] = utility * result[feature]
        interaction_names.append(name)
    return result, interaction_names


def _fit_logistic(
    training: pd.DataFrame,
    numeric_features: list[str],
    categorical_features: list[str],
    *,
    regularization_c: float,
    positive_class_weight: float,
) -> Pipeline:
    estimator = Pipeline(
        [
            (
                "preprocess",
                build_fold_preprocessor(
                    numeric_features=numeric_features,
                    categorical_features=categorical_features,
                    scale_numeric=True,
                ),
            ),
            (
                "model",
                LogisticRegression(
                    C=regularization_c,
                    class_weight={0: 1.0, 1: positive_class_weight},
                    max_iter=2000,
                    random_state=20260802,
                ),
            ),
        ]
    )
    columns = [*numeric_features, *categorical_features]
    estimator.fit(
        training[columns],
        training["deterioration_label"].astype(int),
        model__sample_weight=_equal_sector_sample_weight(training),
    )
    return estimator


def _fit_boosting(
    training: pd.DataFrame,
    numeric_features: list[str],
    categorical_features: list[str],
    parameters: dict[str, Any],
) -> Pipeline:
    """Fit a deliberately small, regularized gradient-boosting challenger."""

    estimator = Pipeline(
        [
            (
                "preprocess",
                build_fold_preprocessor(
                    numeric_features=numeric_features,
                    categorical_features=categorical_features,
                    scale_numeric=False,
                ),
            ),
            (
                "model",
                XGBClassifier(
                    n_estimators=int(parameters["n_estimators"]),
                    max_depth=int(parameters["max_depth"]),
                    learning_rate=float(parameters["learning_rate"]),
                    scale_pos_weight=float(parameters["positive_class_weight"]),
                    min_child_weight=8,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    reg_lambda=2.0,
                    objective="binary:logistic",
                    eval_metric="logloss",
                    random_state=20260802,
                    n_jobs=4,
                ),
            ),
        ]
    )
    columns = [*numeric_features, *categorical_features]
    estimator.fit(
        training[columns],
        training["deterioration_label"].astype(int),
        model__sample_weight=_equal_sector_sample_weight(training),
    )
    return estimator


def _inner_temporal_windows(
    training: pd.DataFrame,
    *,
    minimum_training_quarters: int,
    validation_quarters: int,
    maximum_windows: int,
) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    periods = sorted(training["decision_at"].dt.to_period("Q").unique())
    candidate_positions = range(
        minimum_training_quarters,
        max(len(periods) - validation_quarters + 1, minimum_training_quarters),
        validation_quarters,
    )
    positions = list(candidate_positions)[-maximum_windows:]
    windows: list[tuple[pd.DataFrame, pd.DataFrame]] = []
    for position in positions:
        validation_periods = periods[position : position + validation_quarters]
        if len(validation_periods) < validation_quarters:
            continue
        origin = validation_periods[0].start_time
        fit = training.loc[
            (training["decision_at"] < origin)
            & training["label_available_at"].notna()
            & (training["label_available_at"] < origin)
        ]
        validation = training.loc[
            training["decision_at"].dt.to_period("Q").isin(validation_periods)
        ]
        if (
            fit["deterioration_label"].nunique() == 2
            and validation["deterioration_label"].nunique() == 2
        ):
            windows.append((fit, validation))
    return windows


def nested_select_logistic_policy(
    training: pd.DataFrame,
    numeric_features: list[str],
    categorical_features: list[str],
    config: dict[str, Any],
) -> NestedSelection:
    """Choose regularization and class weight using inner expanding windows."""

    windows = _inner_temporal_windows(
        training,
        minimum_training_quarters=int(config["minimum_inner_training_quarters"]),
        validation_quarters=int(config["inner_validation_window_quarters"]),
        maximum_windows=int(config["inner_validation_windows"]),
    )
    if not windows:
        raise ValueError("Outer training data cannot support nested temporal validation")
    candidates: list[NestedSelection] = []
    columns = [*numeric_features, *categorical_features]
    for regularization_c in config["logistic_c_grid"]:
        for positive_weight in config["class_weight_multipliers"]:
            scores = []
            for fit, validation in windows:
                estimator = _fit_logistic(
                    fit,
                    numeric_features,
                    categorical_features,
                    regularization_c=float(regularization_c),
                    positive_class_weight=float(positive_weight),
                )
                probability = estimator.predict_proba(validation[columns])[:, 1]
                scores.append(
                    average_precision_score(
                        validation["deterioration_label"].astype(int), probability
                    )
                )
            candidates.append(
                NestedSelection(
                    float(regularization_c),
                    float(positive_weight),
                    float(np.mean(scores)),
                    len(scores),
                )
            )
    # Prefer stronger inner PR-AUC, then stronger shrinkage and lower class weight.
    return sorted(
        candidates,
        key=lambda item: (
            -item.mean_inner_pr_auc,
            item.regularization_c,
            item.positive_class_weight,
        ),
    )[0]


def nested_select_boosting_policy(
    training: pd.DataFrame,
    numeric_features: list[str],
    categorical_features: list[str],
    config: dict[str, Any],
) -> BoostingSelection:
    """Select one constrained boosting specification on inner time windows."""

    windows = _inner_temporal_windows(
        training,
        minimum_training_quarters=int(config["minimum_inner_training_quarters"]),
        validation_quarters=int(config["inner_validation_window_quarters"]),
        maximum_windows=int(config["inner_validation_windows"]),
    )
    if not windows:
        raise ValueError("Outer training data cannot support nested boosting validation")
    columns = [*numeric_features, *categorical_features]
    candidates: list[BoostingSelection] = []
    for parameters in config["boosting_candidates"]:
        scores = []
        for fit, validation in windows:
            estimator = _fit_boosting(fit, numeric_features, categorical_features, parameters)
            probability = estimator.predict_proba(validation[columns])[:, 1]
            scores.append(
                average_precision_score(validation["deterioration_label"].astype(int), probability)
            )
        candidates.append(BoostingSelection(dict(parameters), float(np.mean(scores)), len(scores)))
    # If PR-AUC ties, prefer fewer trees and shallower depth.
    return sorted(
        candidates,
        key=lambda item: (
            -item.mean_inner_pr_auc,
            int(item.parameters["n_estimators"]),
            int(item.parameters["max_depth"]),
        ),
    )[0]


def run_nested_logistic_architectures(
    features: pd.DataFrame,
    assignments: pd.DataFrame,
    *,
    numeric_features: list[str],
    categorical_features: list[str],
    config: dict[str, Any],
    selected_features_by_fold: dict[str, list[str]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare the partially pooled primary, pooled benchmark, and boosting challenger."""

    indexed = features.set_index("decision_key", drop=False)
    prediction_rows: list[pd.DataFrame] = []
    selection_rows: list[dict[str, Any]] = []
    architectures = ["pooled", "partially_pooled"]
    prediction_metadata = [
        column
        for column in ["quality_tier", "strict_phase1_certified"]
        if column in features.columns
    ]
    for fold_id in sorted(assignments["fold_id"].unique()):
        fold_numeric_features = (
            selected_features_by_fold[str(fold_id)]
            if selected_features_by_fold is not None
            else numeric_features
        )
        fold = assignments.loc[assignments["fold_id"] == fold_id]
        train_keys = fold.loc[fold["split"] == "TRAIN", "decision_key"]
        validation_keys = fold.loc[fold["split"] == "VALIDATION", "decision_key"]
        outer_training = indexed.loc[train_keys].dropna(subset=["deterioration_label"]).copy()
        outer_validation = (
            indexed.loc[validation_keys].dropna(subset=["deterioration_label"]).copy()
        )
        for architecture in architectures:
            training = outer_training.copy()
            validation = outer_validation.copy()
            model_numeric = list(fold_numeric_features)
            if architecture == "partially_pooled":
                interaction_features = [
                    feature
                    for feature in config["sector_interaction_features"]
                    if feature in model_numeric
                ]
                training, interaction_names = add_prespecified_sector_interactions(
                    training, interaction_features
                )
                validation, _ = add_prespecified_sector_interactions(
                    validation, interaction_features
                )
                model_numeric.extend(interaction_names)
            sector_groups = ["Overall"]
            for sector in sector_groups:
                fit_rows = training
                score_rows = validation
                if score_rows.empty:
                    continue
                selection = nested_select_logistic_policy(
                    fit_rows, model_numeric, categorical_features, config
                )
                estimator = _fit_logistic(
                    fit_rows,
                    model_numeric,
                    categorical_features,
                    regularization_c=selection.regularization_c,
                    positive_class_weight=selection.positive_class_weight,
                )
                probability = estimator.predict_proba(
                    score_rows[[*model_numeric, *categorical_features]]
                )[:, 1]
                output = score_rows[
                    [
                        "decision_key",
                        "cik",
                        "decision_at",
                        "sector",
                        "deterioration_label",
                        *prediction_metadata,
                    ]
                ].copy()
                output["fold_id"] = fold_id
                output["model"] = f"{architecture}_logistic"
                output["probability"] = probability
                prediction_rows.append(output)
                selection_rows.append(
                    {
                        "fold_id": fold_id,
                        "architecture": architecture,
                        "sector_fit": sector,
                        "selected_features": json.dumps(model_numeric),
                        **selection.__dict__,
                    }
                )
        boosting_selection = nested_select_boosting_policy(
            outer_training, fold_numeric_features, categorical_features, config
        )
        boosting = _fit_boosting(
            outer_training,
            fold_numeric_features,
            categorical_features,
            boosting_selection.parameters,
        )
        boosting_output = outer_validation[
            [
                "decision_key",
                "cik",
                "decision_at",
                "sector",
                "deterioration_label",
                *prediction_metadata,
            ]
        ].copy()
        boosting_output["fold_id"] = fold_id
        boosting_output["model"] = "pooled_gradient_boosting"
        boosting_output["probability"] = boosting.predict_proba(
            outer_validation[[*fold_numeric_features, *categorical_features]]
        )[:, 1]
        prediction_rows.append(boosting_output)
        selection_rows.append(
            {
                "fold_id": fold_id,
                "architecture": "pooled_gradient_boosting",
                "sector_fit": "Overall",
                "parameters": json.dumps(boosting_selection.parameters, sort_keys=True),
                "mean_inner_pr_auc": boosting_selection.mean_inner_pr_auc,
                "inner_folds": boosting_selection.inner_folds,
                "selected_features": json.dumps(fold_numeric_features),
            }
        )
    predictions = pd.concat(prediction_rows, ignore_index=True)
    if predictions.duplicated(["decision_key", "fold_id", "model"]).any():
        raise ValueError("Nested modeling produced duplicate out-of-fold predictions")
    return predictions, pd.DataFrame(selection_rows)
