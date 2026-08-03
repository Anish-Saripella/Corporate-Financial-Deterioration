"""Point-in-time joins using information-availability timestamps."""

from __future__ import annotations

import pandas as pd


def asof_join(
    decisions: pd.DataFrame,
    observations: pd.DataFrame,
    *,
    by: str | list[str],
    decision_time: str = "decision_at",
    available_time: str = "available_at",
) -> pd.DataFrame:
    """Attach the latest observation known at each decision timestamp.

    Both input frames are copied and sorted. The original measurement date should remain as a
    separate column; only `available_at` controls eligibility.
    """

    left = decisions.copy()
    right = observations.copy()
    keys = [by] if isinstance(by, str) else by
    for column in [*keys, decision_time]:
        if column not in left:
            raise ValueError(f"Missing decision column: {column}")
    for column in [*keys, available_time]:
        if column not in right:
            raise ValueError(f"Missing observation column: {column}")

    left[decision_time] = pd.to_datetime(left[decision_time], utc=True)
    right[available_time] = pd.to_datetime(right[available_time], utc=True)
    left = left.sort_values([decision_time, *keys]).reset_index(drop=True)
    right = right.sort_values([available_time, *keys]).reset_index(drop=True)
    result = pd.merge_asof(
        left,
        right,
        left_on=decision_time,
        right_on=available_time,
        by=keys,
        direction="backward",
        allow_exact_matches=True,
    )
    known = result[available_time].notna()
    if (result.loc[known, available_time] > result.loc[known, decision_time]).any():
        raise AssertionError("Point-in-time join admitted future information")
    return result
