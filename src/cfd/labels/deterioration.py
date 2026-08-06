"""Candidate four-quarter debt-service deterioration label."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _quarter_positions(group: pd.DataFrame, time_column: str) -> pd.Series:
    if {"fiscal_year", "fiscal_quarter_number"}.issubset(group.columns):
        return group["fiscal_year"].astype(int) * 4 + group["fiscal_quarter_number"].astype(int)
    return pd.to_datetime(group[time_column]).dt.to_period("Q").astype("int64")


def _continuous_future_window(positions: pd.Series, position: int, horizon: int) -> bool:
    window = positions.iloc[position : position + horizon + 1].to_numpy(dtype=int)
    return len(window) == horizon + 1 and bool((np.diff(window) == 1).all())


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
        positions = _quarter_positions(group, time_column)
        for position, index in enumerate(group.index):
            future = coverage.iloc[position + 1 : position + horizon + 1]
            current = coverage.iloc[position]
            if (
                len(future) < horizon
                or not _continuous_future_window(positions, position, horizon)
                or pd.isna(current)
                or current == 0
                or future.isna().any()
            ):
                continue
            future_minimum = float(future.min())
            relative_change = (current - future_minimum) / max(abs(current), np.finfo(float).eps)
            labels.loc[index] = int(
                future_minimum < absolute_threshold and relative_change >= relative_decline
            )
    return labels


def deterioration_diagnostics(
    frame: pd.DataFrame,
    *,
    entity_column: str = "cik",
    time_column: str = "period_end",
    coverage_column: str = "interest_coverage_ttm",
    horizon: int = 4,
    absolute_threshold: float = 1.5,
    relative_decline: float = 0.40,
    cooldown_quarters: int = 4,
) -> pd.DataFrame:
    """Return labels, future-window evidence, availability, and episode starts."""

    result = frame.copy()
    result["deterioration_label"] = make_deterioration_label(
        result,
        entity_column=entity_column,
        time_column=time_column,
        coverage_column=coverage_column,
        horizon=horizon,
        absolute_threshold=absolute_threshold,
        relative_decline=relative_decline,
    )
    result["future_minimum_interest_coverage"] = np.nan
    result["future_interest_coverage_relative_decline"] = np.nan
    result["label_available_at"] = pd.NaT
    result["deterioration_episode_start"] = False
    result["already_below_coverage_threshold"] = result[coverage_column] < absolute_threshold
    ordered = result.sort_values([entity_column, time_column])
    for _, group in ordered.groupby(entity_column, sort=False):
        episode_positions: list[int] = []
        coverage = group[coverage_column].astype(float)
        positions = _quarter_positions(group, time_column)
        for position, index in enumerate(group.index):
            future = coverage.iloc[position + 1 : position + horizon + 1]
            continuous = _continuous_future_window(positions, position, horizon)
            if len(future) == horizon and continuous:
                result.loc[index, "label_available_at"] = group["decision_at"].iloc[
                    position + horizon
                ]
            current = coverage.iloc[position]
            if len(future) < horizon or not continuous or pd.isna(current) or future.isna().any():
                continue
            future_minimum = float(future.min())
            decline = (current - future_minimum) / max(abs(current), np.finfo(float).eps)
            result.loc[index, "future_minimum_interest_coverage"] = future_minimum
            result.loc[index, "future_interest_coverage_relative_decline"] = decline
            if result.loc[index, "deterioration_label"] != 1:
                continue
            quarter_position = int(result.loc[index, "fiscal_year"]) * 4 + int(
                result.loc[index, "fiscal_quarter_number"]
            )
            if (
                not episode_positions
                or quarter_position - episode_positions[-1] >= cooldown_quarters
            ):
                result.loc[index, "deterioration_episode_start"] = True
                episode_positions.append(quarter_position)
    return result
