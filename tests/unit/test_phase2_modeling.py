from __future__ import annotations

import numpy as np
import pandas as pd

from cfd.modeling.phase2 import _equal_sector_sample_weight, run_nested_logistic_architectures


def test_unequal_sample_receives_equal_total_sector_training_weight() -> None:
    frame = pd.DataFrame({"sector": ["Consumer Discretionary"] * 6 + ["Utilities"] * 2})
    weights = _equal_sector_sample_weight(frame)
    weighted = frame.assign(weight=weights).groupby("sector")["weight"].sum()
    assert np.isclose(weighted.iloc[0], weighted.iloc[1])


def test_nested_architectures_produce_one_oof_score_per_model_and_decision() -> None:
    dates = pd.date_range("2014-03-31", periods=36, freq="QE")
    rows = []
    for company in range(4):
        for position, date in enumerate(dates):
            rows.append(
                {
                    "decision_key": f"{company}|{date.date()}",
                    "cik": str(company),
                    "decision_at": date,
                    "label_available_at": date + pd.offsets.QuarterEnd(4),
                    "sector": "Utilities" if company >= 2 else "Consumer Discretionary",
                    "signal": float((position % 4) == 0) + company * 0.01,
                    "deterioration_label": int(position % 4 == 0),
                }
            )
    features = pd.DataFrame(rows)
    assignments = features[["decision_key", "cik", "decision_at"]].copy()
    assignments["fold_id"] = "fold_01"
    assignments["split"] = np.where(
        assignments["decision_at"].isin(dates[-4:]), "VALIDATION", "TRAIN"
    )
    config = {
        "minimum_inner_training_quarters": 12,
        "inner_validation_window_quarters": 4,
        "inner_validation_windows": 2,
        "logistic_c_grid": [0.1, 0.5],
        "class_weight_multipliers": [1.0, 2.0],
        "boosting_candidates": [
            {
                "n_estimators": 10,
                "max_depth": 2,
                "learning_rate": 0.1,
                "positive_class_weight": 1.0,
            }
        ],
        "sector_interaction_features": ["signal"],
    }
    predictions, selections = run_nested_logistic_architectures(
        features,
        assignments,
        numeric_features=["signal"],
        categorical_features=["sector"],
        config=config,
    )
    assert set(predictions["model"]) == {
        "pooled_logistic",
        "partially_pooled_logistic",
        "pooled_gradient_boosting",
    }
    assert not predictions.duplicated(["decision_key", "model"]).any()
    assert len(predictions) == 3 * 4 * 4
    assert set(selections["architecture"]) == {
        "pooled",
        "partially_pooled",
        "pooled_gradient_boosting",
    }
