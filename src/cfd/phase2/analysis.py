"""Build Phase 2 development evidence from real out-of-fold predictions."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from cfd.evaluation.phase2 import (
    add_episode_ids,
    brier_decomposition,
    company_clustered_bootstrap,
    episode_review_metrics,
    expected_decision_value,
    review_queue_metrics,
)
from cfd.modeling.classification import classification_metrics

PREDICTION_COLUMNS = {
    "decision_key",
    "cik",
    "decision_at",
    "sector",
    "deterioration_label",
    "model",
    "probability",
    "fold_id",
}


def development_evidence(
    predictions: pd.DataFrame, config: dict[str, Any]
) -> dict[str, pd.DataFrame]:
    """Create model-comparison tables without opening a final test window."""

    missing = PREDICTION_COLUMNS - set(predictions.columns)
    if missing:
        raise ValueError(f"Predictions are missing required columns: {sorted(missing)}")
    data = predictions.copy()
    data["decision_at"] = pd.to_datetime(data["decision_at"])
    if "feature_increment" in data:
        data["model"] = data["model"].astype(str) + " | " + data["feature_increment"].astype(str)
    if "calibration_method" in data:
        calibration_scope = (
            data["calibration_scope"].astype(str) if "calibration_scope" in data else "overall"
        )
        data["model"] = (
            data["model"].astype(str)
            + " | calibration="
            + data["calibration_method"].astype(str)
            + " | scope="
            + calibration_scope
        )
    if data.duplicated(["decision_key", "model"]).any():
        raise ValueError("Each model must have at most one out-of-fold prediction per decision")
    policy = config["decision_policy"]
    uncertainty = config["uncertainty"]
    review_fractions = policy["review_fractions"]
    metric_rows: list[dict[str, Any]] = []
    queue_rows: list[pd.DataFrame] = []
    episode_rows: list[pd.DataFrame] = []
    bootstrap_rows: list[pd.DataFrame] = []
    value_rows: list[dict[str, Any]] = []
    calibration_rows: list[dict[str, Any]] = []
    for model, model_rows in data.groupby("model", sort=True):
        labels = model_rows["deterioration_label"].to_numpy(dtype=int)
        scores = model_rows["probability"].to_numpy(dtype=float)
        threshold = (
            float(model_rows["threshold"].median())
            if "threshold" in model_rows
            else float(
                np.quantile(
                    scores,
                    1 - float(policy.get("evaluation_reference_alert_rate", 0.20)),
                )
            )
        )
        metric_rows.append(
            {
                "model": model,
                "slice": "Overall",
                "observations": len(model_rows),
                **classification_metrics(labels, scores, threshold),
            }
        )
        for sector, sector_rows in model_rows.groupby("sector", sort=True):
            sector_labels = sector_rows["deterioration_label"].to_numpy(dtype=int)
            sector_scores = sector_rows["probability"].to_numpy(dtype=float)
            metric_rows.append(
                {
                    "model": model,
                    "slice": sector,
                    "observations": len(sector_rows),
                    **classification_metrics(sector_labels, sector_scores, threshold),
                }
            )
        if "quality_tier" in model_rows:
            for tier, tier_rows in model_rows.groupby("quality_tier", sort=True):
                tier_labels = tier_rows["deterioration_label"].to_numpy(dtype=int)
                tier_scores = tier_rows["probability"].to_numpy(dtype=float)
                metric_rows.append(
                    {
                        "model": model,
                        "slice": f"Quality: {tier}",
                        "observations": len(tier_rows),
                        **classification_metrics(tier_labels, tier_scores, threshold),
                    }
                )
        queues = review_queue_metrics(labels, scores, review_fractions)
        queues.insert(0, "model", model)
        queue_rows.append(queues)
        episodes = episode_review_metrics(add_episode_ids(model_rows), review_fractions)
        episodes.insert(0, "model", model)
        episode_rows.append(episodes)
        clustered = company_clustered_bootstrap(
            model_rows,
            cluster_column=str(uncertainty["cluster_column"]),
            repetitions=int(uncertainty["bootstrap_repetitions"]),
            confidence_level=float(uncertainty["confidence_level"]),
            random_seed=int(uncertainty["random_seed"]),
        )
        clustered.insert(0, "model", model)
        bootstrap_rows.append(clustered)
        for fraction in review_fractions:
            cutoff = float(np.quantile(scores, 1 - float(fraction)))
            value_rows.append(
                {
                    "model": model,
                    "review_fraction": float(fraction),
                    "threshold": cutoff,
                    **expected_decision_value(
                        labels,
                        scores >= cutoff,
                        missed_event_cost=float(policy["missed_event_cost"]),
                        unnecessary_review_cost=float(policy["unnecessary_review_cost"]),
                        correct_alert_benefit=float(policy["correct_alert_benefit"]),
                    ),
                }
            )
        for slice_name, slice_rows in [("Overall", model_rows), *model_rows.groupby("sector")]:
            decomposition = brier_decomposition(
                slice_rows["deterioration_label"].to_numpy(dtype=int),
                slice_rows["probability"].to_numpy(dtype=float),
                bins=10,
            )
            calibration_rows.append({"model": model, "slice": slice_name, **decomposition})
    return {
        "metrics": pd.DataFrame(metric_rows),
        "review_queues": pd.concat(queue_rows, ignore_index=True),
        "episode_capture": pd.concat(episode_rows, ignore_index=True),
        "clustered_uncertainty": pd.concat(bootstrap_rows, ignore_index=True),
        "decision_value": pd.DataFrame(value_rows),
        "calibration_decomposition": pd.DataFrame(calibration_rows),
    }
