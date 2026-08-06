from __future__ import annotations

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


def test_episode_ids_combine_consecutive_positive_quarters() -> None:
    frame = pd.DataFrame(
        {
            "cik": ["1"] * 6,
            "decision_at": pd.date_range("2020-03-31", periods=6, freq="QE"),
            "deterioration_label": [0, 1, 1, 0, 1, 1],
        }
    )
    result = add_episode_ids(frame)
    assert result["deterioration_episode_start"].sum() == 2
    assert result["deterioration_episode_id"].dropna().nunique() == 2


def test_review_queue_and_decision_value_are_interpretable() -> None:
    labels = np.array([1, 0, 1, 0, 0, 0, 0, 0, 0, 0])
    probabilities = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05])
    queues = review_queue_metrics(labels, probabilities, [0.2])
    assert queues.iloc[0]["companies_quarters_reviewed"] == 2
    assert queues.iloc[0]["events_captured"] == 1
    value = expected_decision_value(
        labels, probabilities >= 0.7, missed_event_cost=5, unnecessary_review_cost=1
    )
    assert value["true_positive"] == 2
    # Both events are caught, but the middle high-scoring non-event creates one
    # unnecessary review, so net value is -1 under these stated assumptions.
    assert value["net_value"] == -1


def test_company_clustered_bootstrap_is_reproducible() -> None:
    frame = pd.DataFrame(
        {
            "cik": np.repeat(["a", "b", "c", "d"], 4),
            "deterioration_label": [0, 0, 1, 1] * 4,
            "probability": [0.1, 0.2, 0.7, 0.8] * 4,
        }
    )
    first = company_clustered_bootstrap(frame, repetitions=20, random_seed=4)
    second = company_clustered_bootstrap(frame, repetitions=20, random_seed=4)
    pd.testing.assert_frame_equal(first, second)
    assert set(first["metric"]) == {"PR_AUC", "Brier_score"}


def test_episode_capture_counts_runs_instead_of_positive_rows() -> None:
    frame = pd.DataFrame(
        {
            "cik": ["1"] * 6,
            "decision_at": pd.date_range("2020-03-31", periods=6, freq="QE"),
            "deterioration_label": [0, 1, 1, 0, 1, 1],
            "probability": [0.1, 0.9, 0.8, 0.2, 0.7, 0.6],
        }
    )
    result = episode_review_metrics(frame, [0.5])
    assert result.iloc[0]["distinct_episodes"] == 2
    assert result.iloc[0]["episodes_captured"] == 2


def test_brier_decomposition_explains_probability_error() -> None:
    result = brier_decomposition([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9], bins=2)
    assert result["Brier_score"] < 0.1
    assert result["reliability"] >= 0
    assert result["resolution"] >= 0
