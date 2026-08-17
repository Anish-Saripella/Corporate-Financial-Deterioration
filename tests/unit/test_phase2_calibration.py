import numpy as np
import pandas as pd

from cfd.modeling.calibration import ProbabilityCalibrator, cross_fitted_temporal_calibration


def test_all_registered_calibrators_return_probabilities() -> None:
    raw = np.array([0.05, 0.15, 0.25, 0.45, 0.65, 0.75, 0.85, 0.95])
    labels = np.array([0, 0, 0, 1, 0, 1, 1, 1])
    for method in ["none", "intercept", "platt", "isotonic"]:
        calibrated = ProbabilityCalibrator(method).fit(raw, labels).predict(raw)
        assert len(calibrated) == len(raw)
        assert ((calibrated >= 0) & (calibrated <= 1)).all()


def test_calibrator_rejects_one_class_sample() -> None:
    raw = np.array([0.1, 0.2, 0.3])
    labels = np.array([0, 0, 0])
    try:
        ProbabilityCalibrator("platt").fit(raw, labels)
    except ValueError as error:
        assert "both label classes" in str(error)
    else:
        raise AssertionError("One-class calibration should fail")


def test_temporal_calibration_uses_only_earlier_oof_folds() -> None:
    rows = []
    for fold_number in range(3):
        for index in range(6):
            rows.append(
                {
                    "decision_at": pd.Timestamp("2020-01-01")
                    + pd.DateOffset(years=fold_number, months=index),
                    "fold_id": f"fold_{fold_number}",
                    "sector": "Utilities" if index % 2 else "Consumer Discretionary",
                    "deterioration_label": index % 2,
                    "probability": 0.7 if index % 2 else 0.2,
                }
            )
    calibrated = cross_fitted_temporal_calibration(pd.DataFrame(rows), ["none", "platt"])
    assert set(calibrated["fold_id"]) == {"fold_1", "fold_2"}
    assert set(calibrated["calibration_method"]) == {"none", "platt"}
    assert (
        calibrated.loc[calibrated["fold_id"] == "fold_1", "calibration_training_folds"].eq(1).all()
    )
