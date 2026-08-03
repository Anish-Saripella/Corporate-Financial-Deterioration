import numpy as np

from cfd.modeling.classification import classification_metrics, expected_calibration_error


def test_classification_metrics_are_finite_and_bounded() -> None:
    y_true = np.array([0, 0, 0, 1, 1], dtype=int)
    probability = np.array([0.05, 0.2, 0.4, 0.7, 0.9])
    metrics = classification_metrics(y_true, probability, 0.5)
    assert metrics["PR_AUC"] > 0.9
    assert 0 <= metrics["Brier_score"] <= 1
    assert 0 <= expected_calibration_error(y_true, probability) <= 1
