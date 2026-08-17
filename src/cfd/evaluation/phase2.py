"""Phase 2 evaluation tools for correlated company-quarter predictions.

The unit of prediction is a company-quarter, but adjacent rows from one issuer
are not independent.  This module therefore reports operational review-queue
results, distinct deterioration episodes, and uncertainty obtained by
resampling whole issuers rather than individual rows.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.metrics import (  # type: ignore[import-untyped]
    average_precision_score,
    brier_score_loss,
)


def add_episode_ids(
    frame: pd.DataFrame,
    *,
    company_column: str = "cik",
    time_column: str = "decision_at",
    label_column: str = "deterioration_label",
) -> pd.DataFrame:
    """Identify starts of consecutive deterioration runs within each issuer.

    A run of positive quarterly labels is one episode, not four separate
    economic events. Gaps in the panel also start a new episode.
    """

    result = frame.copy()
    result[time_column] = pd.to_datetime(result[time_column])
    result = result.sort_values([company_column, time_column])
    prior_label = (
        pd.to_numeric(
            result.groupby(company_column)[label_column].shift(fill_value=0),
            errors="coerce",
        )
        .fillna(0)
        .astype(int)
    )
    prior_date = result.groupby(company_column)[time_column].shift()
    quarter_gap = result[time_column].dt.to_period("Q").astype("int64") - prior_date.dt.to_period(
        "Q"
    ).astype("int64")
    positive = pd.to_numeric(result[label_column], errors="coerce").fillna(0).astype(int).eq(1)
    result["deterioration_episode_start"] = positive & (prior_label.ne(1) | quarter_gap.ne(1))
    episode_number = result["deterioration_episode_start"].groupby(result[company_column]).cumsum()
    result["deterioration_episode_id"] = pd.Series(pd.NA, index=result.index, dtype="string")
    selected = positive
    result.loc[selected, "deterioration_episode_id"] = (
        result.loc[selected, company_column].astype(str)
        + "|episode_"
        + episode_number.loc[selected].astype(int).astype(str)
    )
    return result.sort_index()


def review_queue_metrics(
    y_true: Sequence[int] | NDArray[Any],
    probabilities: Sequence[float] | NDArray[np.float64],
    review_fractions: Sequence[float] = (0.05, 0.10, 0.20),
) -> pd.DataFrame:
    """Report what an analyst receives at fixed review-capacity levels."""

    labels = np.asarray(y_true, dtype=int)
    scores = np.asarray(probabilities, dtype=float)
    if len(labels) != len(scores) or len(labels) == 0:
        raise ValueError("Labels and probabilities must have the same non-zero length")
    if not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        raise ValueError("Probabilities must be finite values between zero and one")
    total_events = int(labels.sum())
    prevalence = float(labels.mean())
    order = np.argsort(-scores, kind="stable")
    rows: list[dict[str, float | int]] = []
    for fraction in review_fractions:
        if not 0 < fraction <= 1:
            raise ValueError("Each review fraction must be in (0, 1]")
        reviewed = max(int(np.ceil(len(labels) * fraction)), 1)
        captured = int(labels[order[:reviewed]].sum())
        precision = captured / reviewed
        rows.append(
            {
                "review_fraction": float(fraction),
                "companies_quarters_reviewed": reviewed,
                "events_captured": captured,
                "event_capture_rate": captured / total_events if total_events else 0.0,
                "precision": precision,
                "lift_over_random": precision / prevalence if prevalence else 0.0,
            }
        )
    return pd.DataFrame(rows)


def episode_review_metrics(
    predictions: pd.DataFrame,
    review_fractions: Sequence[float] = (0.05, 0.10, 0.20),
    *,
    probability_column: str = "probability",
) -> pd.DataFrame:
    """Measure how many distinct deterioration episodes enter each review queue."""

    data = (
        predictions if "deterioration_episode_id" in predictions else add_episode_ids(predictions)
    )
    episode_ids = set(data["deterioration_episode_id"].dropna().astype(str))
    order = data.sort_values(probability_column, ascending=False, kind="stable")
    rows: list[dict[str, float | int]] = []
    for fraction in review_fractions:
        if not 0 < fraction <= 1:
            raise ValueError("Each review fraction must be in (0, 1]")
        reviewed = max(int(np.ceil(len(data) * fraction)), 1)
        captured = set(order.head(reviewed)["deterioration_episode_id"].dropna().astype(str))
        rows.append(
            {
                "review_fraction": float(fraction),
                "company_quarters_reviewed": reviewed,
                "distinct_episodes": len(episode_ids),
                "episodes_captured": len(captured),
                "episode_capture_rate": len(captured) / len(episode_ids) if episode_ids else 0.0,
            }
        )
    return pd.DataFrame(rows)


def brier_decomposition(
    y_true: Sequence[int] | NDArray[Any],
    probabilities: Sequence[float] | NDArray[np.float64],
    *,
    bins: int = 10,
) -> dict[str, float]:
    """Decompose the Brier score into reliability, resolution, and uncertainty.

    Lower reliability is better (predicted and observed rates agree). Higher
    resolution is better (risk groups differ from the overall event rate).
    With finite bins, the identity is approximate rather than exact.
    """

    labels = np.asarray(y_true, dtype=int)
    scores = _validate_metric_inputs(labels, probabilities)
    prevalence = float(labels.mean())
    boundaries = np.unique(np.quantile(scores, np.linspace(0, 1, bins + 1)))
    if len(boundaries) < 2:
        boundaries = np.array([0.0, 1.0])
    assignments = np.clip(np.digitize(scores, boundaries[1:-1]), 0, len(boundaries) - 2)
    reliability = 0.0
    resolution = 0.0
    for group_id in np.unique(assignments):
        selected = assignments == group_id
        weight = float(selected.mean())
        observed = float(labels[selected].mean())
        predicted = float(scores[selected].mean())
        reliability += weight * (predicted - observed) ** 2
        resolution += weight * (observed - prevalence) ** 2
    uncertainty = prevalence * (1 - prevalence)
    return {
        "Brier_score": float(brier_score_loss(labels, scores)),
        "reliability": reliability,
        "resolution": resolution,
        "uncertainty": uncertainty,
        "decomposition_approximation": reliability - resolution + uncertainty,
    }


def _validate_metric_inputs(
    labels: NDArray[Any], probabilities: Sequence[float] | NDArray[np.float64]
) -> NDArray[np.float64]:
    scores = np.asarray(probabilities, dtype=float)
    if len(labels) != len(scores) or len(labels) == 0:
        raise ValueError("Labels and probabilities must have the same non-zero length")
    if not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        raise ValueError("Probabilities must be finite values between zero and one")
    return scores


def expected_decision_value(
    y_true: Sequence[int] | NDArray[Any],
    alerts: Sequence[bool] | NDArray[np.bool_],
    *,
    missed_event_cost: float,
    unnecessary_review_cost: float,
    correct_alert_benefit: float = 0.0,
) -> dict[str, float | int]:
    """Translate a statistical alert policy into a simple stated-cost result.

    Values are analytical units, not dollars. The cost assumptions must be
    shown beside the result; changing them is a scenario analysis.
    """

    labels = np.asarray(y_true, dtype=int)
    decisions = np.asarray(alerts, dtype=bool)
    if len(labels) != len(decisions):
        raise ValueError("Labels and alerts must have the same length")
    true_positive = int((decisions & (labels == 1)).sum())
    false_positive = int((decisions & (labels == 0)).sum())
    false_negative = int((~decisions & (labels == 1)).sum())
    value = (
        correct_alert_benefit * true_positive
        - unnecessary_review_cost * false_positive
        - missed_event_cost * false_negative
    )
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "net_value": float(value),
        "value_per_observation": float(value / len(labels)) if len(labels) else 0.0,
    }


def _safe_pr_auc(labels: NDArray[np.int_], scores: NDArray[np.float64]) -> float:
    if np.unique(labels).size < 2:
        return np.nan
    return float(average_precision_score(labels, scores))


def company_clustered_bootstrap(
    predictions: pd.DataFrame,
    *,
    cluster_column: str = "cik",
    label_column: str = "deterioration_label",
    probability_column: str = "probability",
    repetitions: int = 500,
    confidence_level: float = 0.95,
    random_seed: int = 20260805,
) -> pd.DataFrame:
    """Estimate metric uncertainty by resampling issuers with replacement.

    All rows belonging to a sampled issuer travel together. Duplicate draws are
    retained as separate clusters, preserving within-company dependence while
    representing uncertainty in which issuers entered the study.
    """

    if repetitions < 2 or not 0 < confidence_level < 1:
        raise ValueError("Use at least two repetitions and confidence_level in (0, 1)")
    companies = predictions[cluster_column].dropna().unique()
    if len(companies) < 2:
        raise ValueError("Clustered uncertainty requires at least two issuers")
    groups = {company: group for company, group in predictions.groupby(cluster_column)}
    rng = np.random.default_rng(random_seed)
    estimates: dict[str, list[float]] = {"PR_AUC": [], "Brier_score": []}
    for _ in range(repetitions):
        sampled = rng.choice(companies, size=len(companies), replace=True)
        replicate = pd.concat([groups[company] for company in sampled], ignore_index=True)
        labels = replicate[label_column].to_numpy(dtype=int)
        scores = replicate[probability_column].to_numpy(dtype=float)
        estimates["PR_AUC"].append(_safe_pr_auc(labels, scores))
        estimates["Brier_score"].append(float(brier_score_loss(labels, scores)))
    alpha = (1 - confidence_level) / 2
    rows: list[dict[str, float | str | int]] = []
    for metric, values in estimates.items():
        clean = np.asarray(values, dtype=float)
        clean = clean[np.isfinite(clean)]
        rows.append(
            {
                "metric": metric,
                "estimate": float(np.mean(clean)),
                "lower": float(np.quantile(clean, alpha)),
                "upper": float(np.quantile(clean, 1 - alpha)),
                "confidence_level": confidence_level,
                "valid_repetitions": len(clean),
            }
        )
    return pd.DataFrame(rows)


def compare_models_clustered(
    predictions: pd.DataFrame,
    *,
    baseline_model: str,
    challenger_model: str,
    model_column: str = "model",
    key_column: str = "decision_key",
    cluster_column: str = "cik",
    repetitions: int = 500,
    random_seed: int = 20260805,
) -> pd.DataFrame:
    """Bootstrap paired challenger-minus-baseline metric differences."""

    subset = predictions.loc[predictions[model_column].isin([baseline_model, challenger_model])]
    wide = subset.pivot(index=key_column, columns=model_column, values="probability")
    metadata = subset.drop_duplicates(key_column).set_index(key_column)
    required = [baseline_model, challenger_model]
    wide = wide.dropna(subset=required).join(
        metadata[[cluster_column, "deterioration_label"]], how="inner"
    )
    companies = wide[cluster_column].unique()
    if len(companies) < 2:
        raise ValueError("Paired comparison requires at least two issuers")
    groups = {company: group for company, group in wide.groupby(cluster_column)}
    rng = np.random.default_rng(random_seed)
    differences: dict[str, list[float]] = {"PR_AUC": [], "Brier_score": []}
    for _ in range(repetitions):
        sampled = rng.choice(companies, size=len(companies), replace=True)
        replicate = pd.concat([groups[company] for company in sampled], ignore_index=True)
        labels = replicate["deterioration_label"].to_numpy(dtype=int)
        base = replicate[baseline_model].to_numpy(dtype=float)
        challenger = replicate[challenger_model].to_numpy(dtype=float)
        if np.unique(labels).size < 2:
            continue
        differences["PR_AUC"].append(
            float(
                average_precision_score(labels, challenger) - average_precision_score(labels, base)
            )
        )
        differences["Brier_score"].append(
            float(brier_score_loss(labels, challenger) - brier_score_loss(labels, base))
        )
    rows = []
    for metric, values in differences.items():
        array = np.asarray(values)
        rows.append(
            {
                "metric": metric,
                "challenger_minus_baseline": float(array.mean()),
                "lower_95": float(np.quantile(array, 0.025)),
                "upper_95": float(np.quantile(array, 0.975)),
                "probability_challenger_better": float(
                    np.mean(array > 0) if metric == "PR_AUC" else np.mean(array < 0)
                ),
            }
        )
    return pd.DataFrame(rows)
