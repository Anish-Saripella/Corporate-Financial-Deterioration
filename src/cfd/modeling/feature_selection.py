"""Leakage-safe, financially constrained feature selection for Phase 2."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score  # type: ignore[import-untyped]

from cfd.modeling.phase2 import _fit_logistic, _inner_temporal_windows


def _correlation_filter(
    training: pd.DataFrame,
    candidates: list[str],
    protected: set[str],
    maximum_absolute_correlation: float,
) -> tuple[list[str], dict[str, str]]:
    """Keep the earlier, simpler feature when two candidates are near-duplicates."""

    retained: list[str] = []
    removed: dict[str, str] = {}
    correlations = training[candidates].corr(method="spearman").abs()
    for feature in candidates:
        conflict = next(
            (
                existing
                for existing in retained
                if float(correlations.loc[feature, existing])  # type: ignore[arg-type]
                >= maximum_absolute_correlation
            ),
            None,
        )
        if conflict is None or feature in protected:
            if feature in protected and conflict is not None and conflict not in protected:
                retained.remove(conflict)
                removed[conflict] = feature
            retained.append(feature)
        else:
            removed[feature] = conflict
    return retained, removed


def select_features_temporally(
    features: pd.DataFrame,
    assignments: pd.DataFrame,
    candidates: list[str],
    config: dict[str, Any],
) -> tuple[dict[str, list[str]], pd.DataFrame]:
    """Select features independently inside every outer temporal training fold.

    The selector combines an economic whitelist, missingness/variance filters,
    correlation pruning, and repeated validation-period permutation importance.
    It never inspects an outer validation outcome. ``selected`` means stable
    predictive relevance in development data, not causal or population-level
    statistical significance.
    """

    policy = config["feature_selection"]
    protected = set(policy["protected_core_features"])
    indexed = features.set_index("decision_key", drop=False)
    selected_by_fold: dict[str, list[str]] = {}
    evidence_rows: list[dict[str, Any]] = []
    for fold_id in sorted(assignments["fold_id"].unique()):
        fold = assignments.loc[assignments["fold_id"] == fold_id]
        train_keys = fold.loc[fold["split"] == "TRAIN", "decision_key"]
        training = indexed.loc[train_keys].dropna(subset=["deterioration_label"]).copy()
        eligible = [
            feature
            for feature in candidates
            if feature in training
            and training[feature].isna().mean() <= float(policy["maximum_missing_rate"])
            and training[feature].nunique(dropna=True) >= 2
        ]
        missing_protected = protected - set(eligible)
        if missing_protected:
            raise ValueError(
                f"Protected core features failed the quality screen: {sorted(missing_protected)}"
            )
        filtered, correlation_removed = _correlation_filter(
            training,
            eligible,
            protected,
            float(policy["maximum_absolute_correlation"]),
        )
        windows = _inner_temporal_windows(
            training,
            minimum_training_quarters=int(config["minimum_inner_training_quarters"]),
            validation_quarters=int(config["inner_validation_window_quarters"]),
            maximum_windows=int(config["inner_validation_windows"]),
        )
        if not windows:
            raise ValueError(f"Feature selection has no valid inner windows for {fold_id}")
        importances: dict[str, list[float]] = {feature: [] for feature in filtered}
        rng = np.random.default_rng(int(policy["random_seed"]))
        for fit_rows, validation_rows in windows:
            estimator = _fit_logistic(
                fit_rows,
                filtered,
                ["sector", "industry"],
                regularization_c=0.10,
                positive_class_weight=2.0,
            )
            columns = [*filtered, "sector", "industry"]
            baseline = average_precision_score(
                validation_rows["deterioration_label"],
                estimator.predict_proba(validation_rows[columns])[:, 1],
            )
            for feature in filtered:
                for _ in range(int(policy["permutation_repeats"])):
                    permuted = validation_rows[columns].copy()
                    permuted[feature] = rng.permutation(permuted[feature].to_numpy())
                    score = average_precision_score(
                        validation_rows["deterioration_label"],
                        estimator.predict_proba(permuted)[:, 1],
                    )
                    importances[feature].append(float(baseline - score))
        ranking: list[tuple[str, float, float]] = []
        for feature in filtered:
            values = np.asarray(importances[feature], dtype=float)
            mean_importance = float(values.mean())
            positive_share = float((values > 0).mean())
            ranking.append((feature, mean_importance, positive_share))
        ranking.sort(key=lambda item: (-item[1], candidates.index(item[0])))
        selected = [
            feature
            for feature, importance, positive_share in ranking
            if feature in protected
            or (importance > 0 and positive_share >= float(policy["minimum_positive_window_share"]))
        ]
        minimum = int(policy["minimum_features"])
        maximum = int(policy["maximum_features"])
        for feature, _, _ in ranking:
            if len(selected) >= minimum:
                break
            if feature not in selected:
                selected.append(feature)
        selected = sorted(
            selected,
            key=lambda feature: next(
                index for index, item in enumerate(ranking) if item[0] == feature
            ),
        )[:maximum]
        selected_by_fold[str(fold_id)] = selected
        selected_set = set(selected)
        ranking_lookup = {feature: (importance, share) for feature, importance, share in ranking}
        for feature in candidates:
            importance, share = ranking_lookup.get(feature, (np.nan, np.nan))
            values = np.asarray(importances.get(feature, []), dtype=float)
            reason = "selected"
            if feature not in eligible:
                reason = "failed_missingness_or_variance_screen"
            elif feature in correlation_removed:
                reason = f"correlated_with:{correlation_removed[feature]}"
            elif feature not in selected_set:
                reason = "insufficient_temporal_permutation_stability"
            evidence_rows.append(
                {
                    "fold_id": fold_id,
                    "feature": feature,
                    "mean_permutation_PR_AUC_loss": importance,
                    "positive_permutation_share": share,
                    "permutation_PR_AUC_loss_p10": float(np.quantile(values, 0.10))
                    if len(values)
                    else np.nan,
                    "permutation_PR_AUC_loss_p90": float(np.quantile(values, 0.90))
                    if len(values)
                    else np.nan,
                    "protected_core": feature in protected,
                    "selected": feature in selected_set,
                    "decision_reason": reason,
                    "outer_validation_used_for_selection": False,
                }
            )
    return selected_by_fold, pd.DataFrame(evidence_rows)
