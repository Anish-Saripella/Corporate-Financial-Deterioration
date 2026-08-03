"""Expanding-window splits with label-horizon embargoes and a locked final holdout."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class TemporalFold:
    fold_id: str
    training_start: str
    training_end: str
    validation_start: str
    validation_end: str
    training_rows: int
    validation_rows: int
    embargoed_rows: int


def build_expanding_window_splits(
    frame: pd.DataFrame,
    *,
    holdout_start: str = "2023-01-01",
    minimum_training_quarters: int = 24,
    validation_window_quarters: int = 4,
    step_quarters: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    """Create annual expanding folds and exclude labels unavailable at each fold origin."""

    data = frame.copy()
    data["decision_at"] = pd.to_datetime(data["decision_at"])
    data["label_available_at"] = pd.to_datetime(data["label_available_at"])
    holdout_boundary = pd.Timestamp(holdout_start)
    development = data.loc[data["decision_at"] < holdout_boundary]
    final_holdout = data.loc[data["decision_at"] >= holdout_boundary].copy()
    final_holdout["split"] = "FINAL_HOLDOUT_LOCKED"

    earliest = development["decision_at"].min().to_period("Q")
    first_validation = (earliest + minimum_training_quarters).start_time
    assignments: list[pd.DataFrame] = []
    fold_records: list[dict[str, Any]] = []
    validation_start = first_validation
    fold_number = 1
    while validation_start < holdout_boundary:
        validation_end = (validation_start.to_period("Q") + validation_window_quarters).start_time
        if validation_end > holdout_boundary:
            break
        train_candidates = development.loc[development["decision_at"] < validation_start]
        train = train_candidates.loc[
            train_candidates["deterioration_label"].notna()
            & train_candidates["label_available_at"].notna()
            & (train_candidates["label_available_at"] < validation_start)
        ].copy()
        embargo = train_candidates.loc[
            train_candidates["deterioration_label"].notna()
            & (
                train_candidates["label_available_at"].isna()
                | (train_candidates["label_available_at"] >= validation_start)
            )
        ].copy()
        validation = development.loc[
            development["decision_at"].between(validation_start, validation_end, inclusive="left")
            & development["deterioration_label"].notna()
        ].copy()
        unique_training_quarters = train["decision_at"].dt.to_period("Q").nunique()
        if unique_training_quarters >= minimum_training_quarters and not validation.empty:
            fold_id = f"fold_{fold_number:02d}"
            for split_name, split_frame in [
                ("TRAIN", train),
                ("EMBARGO", embargo),
                ("VALIDATION", validation),
            ]:
                if split_frame.empty:
                    continue
                assignment = split_frame[["decision_key", "cik", "decision_at"]].copy()
                assignment["fold_id"] = fold_id
                assignment["split"] = split_name
                assignments.append(assignment)
            fold = TemporalFold(
                fold_id=fold_id,
                training_start=str(train["decision_at"].min().date()),
                training_end=str(train["decision_at"].max().date()),
                validation_start=str(validation_start.date()),
                validation_end=str(validation_end.date() - timedelta(days=1)),
                training_rows=len(train),
                validation_rows=len(validation),
                embargoed_rows=len(embargo),
            )
            fold_records.append(asdict(fold))
            fold_number += 1
        validation_start = (validation_start.to_period("Q") + step_quarters).start_time
    if not fold_records:
        raise ValueError("No temporal folds satisfy the configured minimum history")
    assignment_frame = pd.concat(assignments, ignore_index=True)
    for fold_record in fold_records:
        fold_id = fold_record["fold_id"]
        validation_origin = pd.Timestamp(fold_record["validation_start"])
        train_keys = assignment_frame.loc[
            (assignment_frame["fold_id"] == fold_id) & (assignment_frame["split"] == "TRAIN"),
            "decision_key",
        ]
        train_rows = data.set_index("decision_key").loc[train_keys]
        if (train_rows["label_available_at"] >= validation_origin).any():
            raise ValueError(f"Label leakage detected in {fold_id}")
    return assignment_frame, final_holdout, fold_records
