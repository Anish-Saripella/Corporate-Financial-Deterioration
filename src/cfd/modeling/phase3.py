"""Leakage-safe rolling model and ensemble experiments for Phase 3."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import (  # type: ignore[import-untyped]
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.metrics import average_precision_score, roc_auc_score  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.svm import SVC  # type: ignore[import-untyped]
from xgboost import XGBClassifier

from cfd.features.engineering import build_fold_preprocessor
from cfd.modeling.phase2 import _equal_sector_sample_weight


@dataclass(frozen=True)
class RollingFold:
    fold_id: str
    origin: pd.Timestamp
    validation_end: pd.Timestamp


@dataclass
class SectorEstimator:
    """Route rows to estimators trained separately within each sector."""

    estimators: dict[str, Pipeline]
    columns: list[str]

    def predict_proba(self, rows: pd.DataFrame) -> np.ndarray[Any, np.dtype[np.float64]]:
        output = np.zeros((len(rows), 2), dtype=float)
        for sector, estimator in self.estimators.items():
            positions = np.flatnonzero(rows["sector"].eq(sector).to_numpy())
            if len(positions):
                output[positions] = estimator.predict_proba(rows.iloc[positions][self.columns])
        if np.any(output.sum(axis=1) == 0):
            raise ValueError("Sector estimator received an unknown sector")
        return output


HISTORICAL_RISK_FEATURES = [
    "prior_deterioration_rate",
    "prior_deterioration_evidence",
]


def add_contemporaneous_warning_features(features: pd.DataFrame) -> pd.DataFrame:
    """Create simple credit warning indicators known at the decision date."""

    result = features.copy()
    coverage = result["interest_coverage_ttm"]
    result["interest_coverage_buffer_to_1_5"] = coverage - 1.5
    result["interest_coverage_below_1_5"] = coverage.lt(1.5).astype(float)
    result["interest_coverage_below_2_0"] = coverage.lt(2.0).astype(float)
    result["negative_free_cash_flow"] = result["free_cash_flow_margin_ttm"].lt(0).astype(float)
    result["negative_operating_margin"] = result["operating_margin_ttm"].lt(0).astype(float)
    result["current_weakness_signal_count"] = result[
        [
            "interest_coverage_below_1_5",
            "negative_free_cash_flow",
            "negative_operating_margin",
        ]
    ].sum(axis=1)
    return result


def add_prior_deterioration_features(
    training: pd.DataFrame,
    scoring: pd.DataFrame,
    origin: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add issuer history using only labels available before each decision.

    A Beta(1, 4) prior shrinks short issuer histories toward a transparent 20%
    baseline instead of allowing one early event to dominate the estimate.
    """

    fitted = training.copy()
    scored = scoring.copy()
    fitted["prior_deterioration_rate"] = 0.20
    fitted["prior_deterioration_evidence"] = 0.0
    scored["prior_deterioration_rate"] = 0.20
    scored["prior_deterioration_evidence"] = 0.0
    for cik, company in training.groupby("cik", sort=False):
        available = company.sort_values("label_available_at")
        available_dates = available["label_available_at"].to_numpy(dtype="datetime64[ns]")
        labels = available["deterioration_label"].astype(int).to_numpy()
        cumulative = np.concatenate([[0], np.cumsum(labels)])
        company_rows = fitted.loc[fitted["cik"] == cik]
        positions = np.searchsorted(
            available_dates,
            company_rows["decision_at"].to_numpy(dtype="datetime64[ns]"),
            side="left",
        )
        positives = cumulative[positions]
        fitted.loc[company_rows.index, "prior_deterioration_rate"] = (positives + 1.0) / (
            positions + 5.0
        )
        fitted.loc[company_rows.index, "prior_deterioration_evidence"] = np.log1p(positions)
        score_rows = scored.loc[scored["cik"] == cik]
        if score_rows.empty:
            continue
        position = int(np.searchsorted(available_dates, np.datetime64(origin), side="left"))
        rate = (float(cumulative[position]) + 1.0) / (position + 5.0)
        scored.loc[score_rows.index, "prior_deterioration_rate"] = rate
        scored.loc[score_rows.index, "prior_deterioration_evidence"] = np.log1p(position)
    return fitted, scored


def build_phase3_folds(features: pd.DataFrame, config: dict[str, Any]) -> list[RollingFold]:
    """Build quarterly rolling origins whose validation windows remain in development."""

    policy = config["validation"]
    first = pd.Timestamp(policy["first_validation_origin"])
    development_end = pd.Timestamp(policy["development_end"])
    quarters = int(policy["validation_window_quarters"])
    step = int(policy["step_quarters"])
    origins = pd.date_range(first, development_end, freq=f"{step}QS")
    folds: list[RollingFold] = []
    for index, origin in enumerate(origins, start=1):
        validation_end = origin + pd.offsets.QuarterEnd(quarters)
        if validation_end > development_end:
            continue
        validation = features.loc[
            features["decision_at"].between(origin, validation_end, inclusive="both")
            & features["deterioration_label"].notna()
        ]
        if validation["deterioration_label"].nunique() != 2:
            continue
        folds.append(RollingFold(f"phase3_fold_{index:02d}", origin, validation_end))
    if len(folds) < 4:
        raise ValueError("Phase 3 requires at least four rolling development folds")
    return folds


def _training_rows(
    features: pd.DataFrame, origin: pd.Timestamp, config: dict[str, Any]
) -> pd.DataFrame:
    embargo = int(config["validation"]["label_embargo_quarters"])
    latest_decision = origin - pd.offsets.QuarterBegin(embargo)
    rows = features.loc[
        (features["decision_at"] < latest_decision)
        & features["label_available_at"].notna()
        & (features["label_available_at"] < origin)
        & features["deterioration_label"].notna()
    ].copy()
    if rows["deterioration_label"].nunique() != 2:
        raise ValueError(f"Training rows at {origin.date()} do not contain both classes")
    return rows


def screen_features(
    training: pd.DataFrame, candidates: list[str], config: dict[str, Any]
) -> list[str]:
    """Apply fold-local missingness, variance, and correlation screens."""

    policy = config["features"]
    protected = set(policy["protected"])
    eligible = [
        feature
        for feature in candidates
        if feature in training
        and training[feature].isna().mean() <= float(policy["maximum_missing_rate"])
        and training[feature].nunique(dropna=True) >= 2
    ]
    missing = protected - set(eligible)
    if missing:
        raise ValueError(f"Protected Phase 3 features failed screening: {sorted(missing)}")
    correlations = training[eligible].corr(method="spearman").abs()
    retained: list[str] = []
    for feature in eligible:
        conflict = next(
            (
                prior
                for prior in retained
                if float(correlations.at[feature, prior])  # type: ignore[arg-type]
                >= float(policy["maximum_absolute_correlation"])
            ),
            None,
        )
        if conflict is None:
            retained.append(feature)
        elif feature in protected and conflict not in protected:
            retained.remove(conflict)
            retained.append(feature)
    fit_rows, validation_rows = _inner_split(training)
    categorical = [column for column in policy["categorical"] if column in training]
    columns = [*retained, *categorical]
    selector = _pipeline(
        "logistic_l2",
        {"C": 0.10, "positive_weight": 1.0},
        retained,
        categorical,
        int(config["random_seed"]),
    )
    _fit(selector, fit_rows, columns)
    labels = validation_rows["deterioration_label"].astype(int)
    baseline = float(roc_auc_score(labels, selector.predict_proba(validation_rows[columns])[:, 1]))
    rng = np.random.default_rng(int(config["random_seed"]))
    relevance: dict[str, float] = {}
    for feature in retained:
        losses: list[float] = []
        for _ in range(3):
            permuted = validation_rows[columns].copy()
            permuted[feature] = rng.permutation(permuted[feature].to_numpy())
            score = float(roc_auc_score(labels, selector.predict_proba(permuted)[:, 1]))
            losses.append(baseline - score)
        relevance[feature] = float(np.mean(losses))
    retained.sort(
        key=lambda feature: (
            feature not in protected,
            -relevance[feature],
            candidates.index(feature),
        )
    )
    maximum = int(policy["maximum_features"])
    minimum = int(policy["minimum_features"])
    if len(retained) < minimum:
        raise ValueError(f"Only {len(retained)} Phase 3 features survived fold-local screening")
    selected = [feature for feature in retained if feature in protected or relevance[feature] > 0]
    for feature in retained:
        if len(selected) >= minimum:
            break
        if feature not in selected:
            selected.append(feature)
    return selected[:maximum]


def _pipeline(
    model_name: str,
    parameters: dict[str, Any],
    numeric_features: list[str],
    categorical_features: list[str],
    seed: int,
) -> Pipeline:
    scale = model_name.startswith("logistic") or model_name == "rbf_svc"
    preprocess = build_fold_preprocessor(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        scale_numeric=scale,
    )
    if model_name == "logistic_l2":
        model: Any = LogisticRegression(
            C=float(parameters["C"]),
            class_weight={0: 1.0, 1: float(parameters["positive_weight"])},
            max_iter=3000,
            random_state=seed,
        )
    elif model_name == "logistic_elastic_net":
        model = LogisticRegression(
            C=float(parameters["C"]),
            penalty="elasticnet",
            l1_ratio=float(parameters["l1_ratio"]),
            solver="saga",
            class_weight={0: 1.0, 1: float(parameters["positive_weight"])},
            max_iter=4000,
            random_state=seed,
        )
    elif model_name == "random_forest":
        model = RandomForestClassifier(
            **parameters,
            class_weight="balanced_subsample",
            n_jobs=4,
            random_state=seed,
        )
    elif model_name == "extra_trees":
        model = ExtraTreesClassifier(
            **parameters,
            class_weight="balanced",
            n_jobs=4,
            random_state=seed,
        )
    elif model_name == "histogram_gradient_boosting":
        preprocess.sparse_threshold = 0.0
        model = HistGradientBoostingClassifier(**parameters, random_state=seed)
    elif model_name == "xgboost":
        model = XGBClassifier(
            **parameters,
            objective="binary:logistic",
            eval_metric="logloss",
            n_jobs=4,
            random_state=seed,
        )
    elif model_name == "rbf_svc":
        model = SVC(
            **parameters,
            class_weight="balanced",
            probability=True,
            random_state=seed,
        )
    else:
        raise ValueError(f"Unknown Phase 3 model: {model_name}")
    return Pipeline([("preprocess", preprocess), ("model", model)])


def _fit(
    estimator: Pipeline,
    training: pd.DataFrame,
    columns: list[str],
) -> Pipeline:
    weights = _equal_sector_sample_weight(training)
    model = estimator.named_steps["model"]
    if isinstance(model, HistGradientBoostingClassifier):
        labels = training["deterioration_label"].astype(int).to_numpy()
        positive = labels == 1
        class_factor = len(labels) / max(2 * int(positive.sum()), 1)
        weights = weights * np.where(positive, class_factor, 1.0)
    estimator.fit(
        training[columns],
        training["deterioration_label"].astype(int),
        model__sample_weight=weights,
    )
    return estimator


def _inner_split(training: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    periods = sorted(training["decision_at"].dt.to_period("Q").unique())
    if len(periods) < 12:
        raise ValueError("Insufficient history for Phase 3 inner validation")
    validation_periods = periods[-4:]
    origin = validation_periods[0].start_time
    fit = training.loc[
        (training["decision_at"] < origin)
        & training["label_available_at"].notna()
        & (training["label_available_at"] < origin)
    ]
    validation = training.loc[training["decision_at"].dt.to_period("Q").isin(validation_periods)]
    if (
        fit["deterioration_label"].nunique() != 2
        or validation["deterioration_label"].nunique() != 2
    ):
        raise ValueError("Inner validation split does not contain both classes")
    return fit, validation


def select_and_fit_models(
    training: pd.DataFrame,
    numeric_features: list[str],
    categorical_features: list[str],
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, float], list[dict[str, Any]]]:
    """Tune each family on a prior inner window, then refit on the outer training data."""

    fit_rows, validation_rows = _inner_split(training)
    columns = [*numeric_features, *categorical_features]
    fitted: dict[str, Any] = {}
    scores: dict[str, float] = {}
    selections: list[dict[str, Any]] = []
    seed = int(config["random_seed"])
    sector_families = set(config["models"].get("sector_specific_families", []))
    for model_name, grid in config["models"].items():
        if model_name == "sector_specific_families":
            continue
        candidates: list[tuple[float, float, dict[str, Any]]] = []
        for parameters in grid:
            estimator = _pipeline(
                model_name, dict(parameters), numeric_features, categorical_features, seed
            )
            _fit(estimator, fit_rows, columns)
            probability = estimator.predict_proba(validation_rows[columns])[:, 1]
            roc = float(roc_auc_score(validation_rows["deterioration_label"], probability))
            pr = float(average_precision_score(validation_rows["deterioration_label"], probability))
            candidates.append((roc, pr, dict(parameters)))
        roc, pr, selected = sorted(candidates, key=lambda item: (-item[0], -item[1]))[0]
        estimator = _pipeline(model_name, selected, numeric_features, categorical_features, seed)
        fitted[model_name] = _fit(estimator, training, columns)
        scores[model_name] = roc
        selections.append(
            {
                "model": model_name,
                "inner_ROC_AUC": roc,
                "inner_PR_AUC": pr,
                "parameters": json.dumps(selected, sort_keys=True),
            }
        )
    for family in sorted(sector_families):
        sector_estimators: dict[str, Pipeline] = {}
        selected_by_sector: dict[str, dict[str, Any]] = {}
        inner_probability = np.zeros(len(validation_rows), dtype=float)
        for sector in sorted(training["sector"].unique()):
            sector_fit = fit_rows.loc[fit_rows["sector"] == sector]
            sector_validation = validation_rows.loc[validation_rows["sector"] == sector]
            if (
                sector_fit["deterioration_label"].nunique() != 2
                or sector_validation["deterioration_label"].nunique() != 2
            ):
                raise ValueError(f"Sector-specific {family} lacks both classes for {sector}")
            candidates = []
            for parameters in config["models"][family]:
                estimator = _pipeline(
                    family, dict(parameters), numeric_features, categorical_features, seed
                )
                _fit(estimator, sector_fit, columns)
                probability = estimator.predict_proba(sector_validation[columns])[:, 1]
                candidates.append(
                    (
                        float(roc_auc_score(sector_validation["deterioration_label"], probability)),
                        float(
                            average_precision_score(
                                sector_validation["deterioration_label"], probability
                            )
                        ),
                        dict(parameters),
                    )
                )
            _, _, selected = sorted(candidates, key=lambda item: (-item[0], -item[1]))[0]
            selected_by_sector[sector] = selected
            outer_sector = training.loc[training["sector"] == sector]
            sector_estimator = _pipeline(
                family, selected, numeric_features, categorical_features, seed
            )
            sector_estimators[sector] = _fit(sector_estimator, outer_sector, columns)
            temporary = _pipeline(family, selected, numeric_features, categorical_features, seed)
            _fit(temporary, sector_fit, columns)
            mask = validation_rows["sector"].eq(sector).to_numpy()
            inner_probability[mask] = temporary.predict_proba(validation_rows.loc[mask, columns])[
                :, 1
            ]
        model_name = f"sector_specific_{family}"
        fitted[model_name] = SectorEstimator(sector_estimators, columns)
        roc = float(roc_auc_score(validation_rows["deterioration_label"], inner_probability))
        pr = float(
            average_precision_score(validation_rows["deterioration_label"], inner_probability)
        )
        scores[model_name] = roc
        selections.append(
            {
                "model": model_name,
                "inner_ROC_AUC": roc,
                "inner_PR_AUC": pr,
                "parameters": json.dumps(selected_by_sector, sort_keys=True),
            }
        )
    return fitted, scores, selections


def shrunk_performance_weights(scores: dict[str, float], shrinkage: float) -> dict[str, float]:
    """Convert ROC-AUC evidence into stable nonnegative weights."""

    names = sorted(scores)
    evidence = np.asarray([max(scores[name] - 0.5, 0.001) for name in names], dtype=float)
    evidence /= evidence.sum()
    equal = np.full(len(names), 1.0 / len(names))
    weights = (1.0 - shrinkage) * evidence + shrinkage * equal
    return dict(zip(names, weights, strict=True))


def run_phase3_development(
    features: pd.DataFrame,
    candidate_features: list[str],
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create base and leakage-safe ensemble OOF predictions."""

    data = add_contemporaneous_warning_features(features)
    data["decision_at"] = pd.to_datetime(data["decision_at"])
    data["label_available_at"] = pd.to_datetime(data["label_available_at"])
    folds = build_phase3_folds(data, config)
    categorical = [column for column in config["features"]["categorical"] if column in data]
    prediction_frames: list[pd.DataFrame] = []
    selection_rows: list[dict[str, Any]] = []
    historical_scores: list[tuple[pd.Timestamp, dict[str, float]]] = []
    historical_prediction_frames: list[pd.DataFrame] = []
    weight_rows: list[dict[str, Any]] = []
    for fold in folds:
        training = _training_rows(data, fold.origin, config)
        validation = data.loc[
            data["decision_at"].between(fold.origin, fold.validation_end, inclusive="both")
            & data["deterioration_label"].notna()
        ].copy()
        training, validation = add_prior_deterioration_features(training, validation, fold.origin)
        numeric = screen_features(
            training, [*candidate_features, *HISTORICAL_RISK_FEATURES], config
        )
        models, inner_scores, selections = select_and_fit_models(
            training, numeric, categorical, config
        )
        columns = [*numeric, *categorical]
        base = validation[
            ["decision_key", "cik", "decision_at", "sector", "deterioration_label"]
        ].copy()
        base["fold_id"] = fold.fold_id
        base["origin"] = fold.origin
        probability_columns: dict[str, np.ndarray[Any, Any]] = {}
        for model_name, estimator in models.items():
            probability = estimator.predict_proba(validation[columns])[:, 1]
            probability_columns[model_name] = probability
            output = base.copy()
            output["model"] = model_name
            output["probability"] = probability
            prediction_frames.append(output)
        matrix = np.column_stack([probability_columns[name] for name in sorted(models)])
        simple = matrix.mean(axis=1)
        ranks = pd.DataFrame(matrix).rank(pct=True).mean(axis=1).to_numpy()
        top_three_names = sorted(inner_scores, key=lambda name: inner_scores[name], reverse=True)[
            :3
        ]
        top_three = np.column_stack([probability_columns[name] for name in top_three_names]).mean(
            axis=1
        )
        inner_winner = probability_columns[top_three_names[0]]
        sector_weight = float(config["ensembles"]["xgb_sector_specific_weight"])
        xgb_sector_blend = (1.0 - sector_weight) * probability_columns[
            "xgboost"
        ] + sector_weight * probability_columns["sector_specific_xgboost"]
        xgb_rf_blend = (
            0.70 * probability_columns["xgboost"] + 0.30 * probability_columns["random_forest"]
        )
        static_weights = shrunk_performance_weights(
            inner_scores, float(config["ensembles"]["static_equal_weight_shrinkage"])
        )
        completed_scores = [
            scores for validation_end, scores in historical_scores if validation_end < fold.origin
        ]
        if completed_scores:
            decay = float(config["ensembles"]["adaptive_decay"])
            aggregate: dict[str, float] = {}
            for model_name in sorted(models):
                values = [row[model_name] for row in completed_scores]
                temporal_weights = np.asarray(
                    [decay**index for index in reversed(range(len(values)))], dtype=float
                )
                aggregate[model_name] = float(np.average(values, weights=temporal_weights))
            adaptive_weights = shrunk_performance_weights(
                aggregate, float(config["ensembles"]["adaptive_equal_weight_shrinkage"])
            )
        else:
            adaptive_weights = static_weights
        static = sum(probability_columns[name] * weight for name, weight in static_weights.items())
        adaptive = sum(
            probability_columns[name] * weight for name, weight in adaptive_weights.items()
        )
        completed_predictions = [
            frame
            for frame in historical_prediction_frames
            if pd.Timestamp(frame["validation_end"].iloc[0]) < fold.origin
        ]
        if completed_predictions:
            meta_training = pd.concat(completed_predictions, ignore_index=True)
            meta_columns = sorted(models)
            meta = LogisticRegression(
                C=0.10, max_iter=2000, random_state=int(config["random_seed"])
            )
            meta.fit(meta_training[meta_columns], meta_training["deterioration_label"].astype(int))
            stacking = meta.predict_proba(pd.DataFrame(probability_columns)[meta_columns])[:, 1]
        else:
            stacking = simple
        for ensemble_name, probability in {
            "ensemble_simple_average": simple,
            "ensemble_rank_average": ranks,
            "ensemble_top3_average": top_three,
            "ensemble_inner_winner": inner_winner,
            "ensemble_xgb_sector_blend": xgb_sector_blend,
            "ensemble_xgb_rf_blend": xgb_rf_blend,
            "ensemble_static_weighted": static,
            "ensemble_adaptive_weighted": adaptive,
            "ensemble_stacking": stacking,
        }.items():
            output = base.copy()
            output["model"] = ensemble_name
            output["probability"] = probability
            prediction_frames.append(output)
        labels = validation["deterioration_label"].astype(int)
        fold_scores = {
            name: float(roc_auc_score(labels, probability))
            for name, probability in probability_columns.items()
        }
        historical_scores.append((fold.validation_end, fold_scores))
        history_frame = pd.DataFrame(probability_columns)
        history_frame["deterioration_label"] = labels.to_numpy()
        history_frame["validation_end"] = fold.validation_end
        historical_prediction_frames.append(history_frame)
        for selection in selections:
            selection_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "origin": fold.origin,
                    "validation_end": fold.validation_end,
                    "features": json.dumps(numeric),
                    **selection,
                }
            )
        for weight_type, weights in {
            "static": static_weights,
            "adaptive": adaptive_weights,
        }.items():
            for model_name, weight in weights.items():
                weight_rows.append(
                    {
                        "fold_id": fold.fold_id,
                        "origin": fold.origin,
                        "weight_type": weight_type,
                        "model": model_name,
                        "weight": weight,
                        "past_outer_windows_used": len(completed_scores),
                    }
                )
    predictions = pd.concat(prediction_frames, ignore_index=True)
    if predictions.duplicated(["decision_key", "fold_id", "model"]).any():
        raise ValueError("Phase 3 produced duplicate fold-model predictions")
    return predictions, pd.DataFrame(selection_rows), pd.DataFrame(weight_rows)
