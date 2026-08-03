"""Fiscal-quarter standardization that preserves actual dates and data provenance."""

from __future__ import annotations

import pandas as pd

REQUIRED_FISCAL_COLUMNS = {
    "cik",
    "fiscal_year",
    "fiscal_quarter",
    "period_end",
    "filed_at",
    "accession_number",
}
VALID_FISCAL_QUARTERS = {"FQ1", "FQ2", "FQ3", "FQ4"}


def validate_fiscal_index(frame: pd.DataFrame) -> None:
    """Reject fiscal labels that discard dates or filing provenance."""

    missing = REQUIRED_FISCAL_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Missing fiscal-index columns: {sorted(missing)}")
    invalid = set(frame["fiscal_quarter"].dropna().unique()) - VALID_FISCAL_QUARTERS
    if invalid:
        raise ValueError(f"Invalid fiscal-quarter labels: {sorted(invalid)}")
    period_end = pd.to_datetime(frame["period_end"], errors="coerce", utc=True)
    filed_at = pd.to_datetime(frame["filed_at"], errors="coerce", utc=True)
    if period_end.isna().any() or filed_at.isna().any():
        raise ValueError("period_end and filed_at must be valid timestamps")
    if (filed_at < period_end).any():
        raise ValueError("A filing cannot be available before its reporting period ends")


def derive_fourth_quarter(
    annual_value: float,
    first_quarter: float,
    second_quarter: float,
    third_quarter: float,
) -> float:
    """Derive a duration-flow FQ4 from the annual value and first three quarters."""

    return annual_value - first_quarter - second_quarter - third_quarter
