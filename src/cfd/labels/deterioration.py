"""Candidate four-quarter debt-service deterioration label."""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_deterioration_label(
    frame: pd.DataFrame,
    *,
    entity_column: str = "cik",
    time_column: str = "period_end",
    coverage_column: str = "interest_coverage_ttm",
    horizon: int = 4,
    absolute_threshold: float = 1.5,
    relative_decline: float = 0.40,
) -> pd.Series:
    """Label whether coverage breaches both absolute and relative rules in the future window."""

    required = {entity_column, time_column, coverage_column}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing label columns: {sorted(missing)}")
    if horizon < 1 or not 0 < relative_decline < 1:
        raise ValueError("Invalid horizon or relative-decline threshold")

    ordered = frame.sort_values([entity_column, time_column])
    labels = pd.Series(pd.NA, index=frame.index, dtype="Int8")
    for _, group in ordered.groupby(entity_column, sort=False):
        coverage = group[coverage_column].astype(float)
        for position, index in enumerate(group.index):
            future = coverage.iloc[position + 1 : position + horizon + 1]
            current = coverage.iloc[position]
            if len(future) < horizon or pd.isna(current) or current == 0 or future.isna().any():
                continue
            future_minimum = float(future.min())
            relative_change = (current - future_minimum) / max(abs(current), np.finfo(float).eps)
            labels.loc[index] = int(
                future_minimum < absolute_threshold and relative_change >= relative_decline
            )
    return labels
