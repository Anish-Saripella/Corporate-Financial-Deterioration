"""Financial-history eligibility audit for the candidate issuer universe."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

CORE_FIELDS = [
    "revenue",
    "operating_income",
    "interest_expense",
    "operating_cash_flow",
    "capital_expenditures",
    "total_assets",
    "total_debt",
]
ESSENTIAL_FIELDS = ["operating_income", "interest_expense", "total_assets", "total_debt"]


def _maximum_consecutive_quarters(frame: pd.DataFrame, usable: pd.Series) -> int:
    if frame.empty:
        return 0
    positions = frame["fiscal_year"].astype(int) * 4 + frame["fiscal_quarter_number"].astype(int)
    usable_positions = positions.loc[usable].drop_duplicates().sort_values().tolist()
    maximum = current = 0
    previous: int | None = None
    for position in usable_positions:
        current = current + 1 if previous is not None and position == previous + 1 else 1
        maximum = max(maximum, current)
        previous = position
    return maximum


def audit_company_eligibility(
    metadata: pd.DataFrame,
    quarterly: pd.DataFrame,
    *,
    minimum_usable_quarters: int = 24,
    minimum_consecutive_quarters: int = 16,
    minimum_coverage: float = 0.80,
    minimum_interest_expense: float = 1_000_000,
    minimum_interest_quarters: int = 12,
) -> pd.DataFrame:
    """Apply prespecified, outcome-independent financial-history rules."""

    rows: list[dict[str, object]] = []
    for metadata_row in metadata.itertuples(index=False):
        cik = str(metadata_row.cik).zfill(10)
        company = quarterly.loc[quarterly["cik"] == cik].copy()
        company = company.loc[company["fiscal_year"].between(2012, 2025)]
        for field in CORE_FIELDS:
            if field not in company:
                company[field] = np.nan
        if company.empty:
            coverage = 0.0
            usable = pd.Series(dtype=bool)
            interest_quarters = 0
        else:
            coverage = float(company[CORE_FIELDS].notna().to_numpy().mean())
            row_coverage = company[CORE_FIELDS].notna().mean(axis=1)
            usable = (row_coverage >= minimum_coverage) & company[ESSENTIAL_FIELDS].notna().all(
                axis=1
            )
            interest_quarters = int(
                (company["interest_expense"].abs() >= minimum_interest_expense).sum()
            )
        usable_quarters = int(usable.sum())
        consecutive = _maximum_consecutive_quarters(company, usable)
        reasons: list[str] = []
        if usable_quarters < minimum_usable_quarters:
            reasons.append("INSUFFICIENT_USABLE_QUARTERS")
        if consecutive < minimum_consecutive_quarters:
            reasons.append("INSUFFICIENT_CONSECUTIVE_QUARTERS")
        if coverage < minimum_coverage:
            reasons.append("INSUFFICIENT_CORE_FIELD_COVERAGE")
        if interest_quarters < minimum_interest_quarters:
            reasons.append("INSUFFICIENT_INTEREST_EXPENSE_HISTORY")
        development = company.loc[company["fiscal_year"] <= 2023]
        rows.append(
            {
                "cik": cik,
                "company_name": metadata_row.company_name,
                "ticker": metadata_row.ticker,
                "exchange": metadata_row.exchange,
                "sic": metadata_row.sic,
                "sector": metadata_row.sector,
                "industry": metadata_row.industry,
                "usable_quarters": usable_quarters,
                "maximum_consecutive_usable_quarters": consecutive,
                "core_field_coverage": coverage,
                "meaningful_interest_expense_quarters": interest_quarters,
                "median_total_assets": development["total_assets"].median(),
                "median_revenue": development["revenue"].median(),
                "eligible": not reasons,
                "reason_codes": json.dumps(reasons if reasons else ["ELIGIBLE"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["sector", "industry", "cik"])
