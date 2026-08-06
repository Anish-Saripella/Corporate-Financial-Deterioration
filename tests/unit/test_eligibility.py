import pandas as pd

from cfd.eligibility import CORE_FIELDS, audit_company_eligibility


def test_eligibility_requires_complete_prespecified_history() -> None:
    metadata = pd.DataFrame(
        {
            "cik": ["0000000001"],
            "company_name": ["Example"],
            "ticker": ["EX"],
            "exchange": ["NYSE"],
            "sic": [4911],
            "sector": ["Utilities"],
            "industry": ["Electric Utilities"],
        }
    )
    rows = []
    for position in range(28):
        row = {
            "cik": "0000000001",
            "fiscal_year": 2017 + position // 4,
            "fiscal_quarter_number": position % 4 + 1,
        }
        row.update({field: 10_000_000.0 for field in CORE_FIELDS})
        rows.append(row)
    result = audit_company_eligibility(metadata, pd.DataFrame(rows))
    assert bool(result.loc[0, "eligible"])
    assert result.loc[0, "usable_quarters"] == 28
    assert result.loc[0, "maximum_consecutive_usable_quarters"] == 28


def test_company_quarter_mode_allows_optional_gaps_with_reliable_coverage() -> None:
    metadata = pd.DataFrame(
        {
            "cik": ["0000000001"],
            "company_name": ["Example"],
            "ticker": ["EX"],
            "exchange": ["NYSE"],
            "sic": [4911],
            "sector": ["Utilities"],
            "industry": ["Electric Utilities"],
        }
    )
    rows = []
    for position in range(20):
        rows.append(
            {
                "cik": "0000000001",
                "fiscal_year": 2018 + position // 4,
                "fiscal_quarter_number": position % 4 + 1,
                "operating_income": 20_000_000.0 if position != 8 else None,
                "interest_expense": 2_000_000.0 if position != 8 else None,
                "total_assets": 100_000_000.0 if position < 12 else None,
                "revenue": 50_000_000.0,
            }
        )
    result = audit_company_eligibility(
        metadata,
        pd.DataFrame(rows),
        eligibility_mode="company_quarter",
        minimum_interest_coverage_quarters=16,
        minimum_consecutive_interest_coverage_quarters=8,
        minimum_total_assets_quarters=12,
    )
    assert bool(result.loc[0, "eligible"])
    assert result.loc[0, "maximum_consecutive_interest_coverage_quarters"] >= 8
