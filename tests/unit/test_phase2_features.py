from __future__ import annotations

import numpy as np
import pandas as pd

from cfd.features.phase2 import engineer_phase2_financial_features


def test_phase2_features_are_backward_looking_and_financially_interpretable() -> None:
    dates = pd.date_range("2018-03-31", periods=10, freq="QE")
    panel = pd.DataFrame(
        {
            "cik": ["1"] * 10,
            "decision_at": dates + pd.Timedelta(45, unit="D"),
            "period_end": dates,
            "sector": ["Utilities"] * 10,
            "short_term_debt": np.arange(10, 20, dtype=float),
            "total_debt": np.arange(100, 110, dtype=float),
            "cash_and_equivalents": np.full(10, 5.0),
            "total_assets": np.full(10, 200.0),
            "current_assets": np.full(10, 50.0),
            "current_liabilities": np.full(10, 40.0),
            "interest_expense_ttm": np.arange(10, 20, dtype=float),
            "capital_expenditures_ttm": np.full(10, 8.0),
            "operating_cash_flow_ttm": np.full(10, 20.0),
            "operating_income_ttm": np.full(10, 25.0),
            "revenue_ttm": np.arange(100, 110, dtype=float),
            "net_income_ttm": np.full(10, 10.0),
            "operating_margin_ttm": np.full(10, 0.2),
            "current_ratio": np.full(10, 1.25),
            "interest_coverage_ttm": np.linspace(4, 2, 10),
            "free_cash_flow_margin_ttm": np.full(10, 0.1),
            "total_debt_to_assets": np.arange(100, 110) / 200,
            "preferred_tag_share": np.full(10, 0.9),
            "derived_fact_share": np.full(10, 0.1),
            "maximum_source_available_at": dates + pd.Timedelta(45, unit="D"),
        }
    )
    result = engineer_phase2_financial_features(panel)
    assert np.isclose(result.iloc[-1]["short_term_debt_share"], 19 / 109)
    assert np.isclose(result.iloc[-1]["working_capital_to_assets"], 0.05)
    assert result.iloc[:4]["revenue_growth_yoy"].isna().all()
    assert result.iloc[4:]["revenue_growth_yoy"].notna().all()
    assert result["source_quality_score"].between(0, 1).all()


def test_phase2_features_reject_future_information() -> None:
    dates = pd.date_range("2020-03-31", periods=4, freq="QE")
    # Reuse a complete valid shape and then make one source availability date future.
    base = {
        "cik": ["1"] * 4,
        "decision_at": dates,
        "period_end": dates - pd.Timedelta(45, unit="D"),
        "sector": ["Utilities"] * 4,
    }
    for column in [
        "short_term_debt",
        "total_debt",
        "cash_and_equivalents",
        "total_assets",
        "current_assets",
        "current_liabilities",
        "interest_expense_ttm",
        "capital_expenditures_ttm",
        "operating_cash_flow_ttm",
        "operating_income_ttm",
        "revenue_ttm",
        "net_income_ttm",
        "operating_margin_ttm",
        "current_ratio",
        "interest_coverage_ttm",
        "free_cash_flow_margin_ttm",
        "total_debt_to_assets",
        "preferred_tag_share",
        "derived_fact_share",
    ]:
        base[column] = [1.0] * 4
    base["maximum_source_available_at"] = dates
    frame = pd.DataFrame(base)
    frame.loc[0, "maximum_source_available_at"] = frame.loc[0, "decision_at"] + pd.Timedelta(1, "d")
    try:
        engineer_phase2_financial_features(frame)
    except ValueError as error:
        assert "future-available" in str(error)
    else:
        raise AssertionError("Future-available input must fail")
