"""Numerically guarded financial KPI definitions."""

from __future__ import annotations

import numpy as np
import pandas as pd


def safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Return a ratio while treating zero and non-finite results as missing."""

    denominator_clean = denominator.replace(0, np.nan)
    result = numerator / denominator_clean
    return result.replace([np.inf, -np.inf], np.nan)


def interest_coverage(
    operating_income_ttm: pd.Series, interest_expense_ttm: pd.Series
) -> pd.Series:
    return safe_ratio(operating_income_ttm, interest_expense_ttm)


def free_cash_flow_margin(
    operating_cash_flow_ttm: pd.Series,
    capital_expenditures_ttm: pd.Series,
    revenue_ttm: pd.Series,
) -> pd.Series:
    return safe_ratio(operating_cash_flow_ttm - capital_expenditures_ttm, revenue_ttm)


def total_debt_to_assets(
    short_term_debt: pd.Series,
    long_term_debt: pd.Series,
    total_assets: pd.Series,
) -> pd.Series:
    return safe_ratio(short_term_debt.fillna(0) + long_term_debt.fillna(0), total_assets)
