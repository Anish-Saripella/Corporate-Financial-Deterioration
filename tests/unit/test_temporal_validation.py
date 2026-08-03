from __future__ import annotations

import pandas as pd

from cfd.evaluation.temporal import build_expanding_window_splits


def test_temporal_splits_embargo_unavailable_training_labels() -> None:
    dates = pd.date_range("2010-03-31", "2022-12-31", freq="QE")
    frame = pd.DataFrame(
        {
            "decision_key": [f"1|{index}" for index in range(len(dates))],
            "cik": ["1"] * len(dates),
            "decision_at": dates,
            "label_available_at": dates + pd.offsets.QuarterEnd(4),
            "deterioration_label": [0] * len(dates),
        }
    )

    assignments, holdout, folds = build_expanding_window_splits(frame, holdout_start="2023-01-01")

    assert folds
    assert holdout.empty
    for fold in folds:
        training_keys = assignments.loc[
            (assignments["fold_id"] == fold["fold_id"]) & (assignments["split"] == "TRAIN"),
            "decision_key",
        ]
        training = frame.set_index("decision_key").loc[training_keys]
        assert (training["label_available_at"] < pd.Timestamp(fold["validation_start"])).all()
