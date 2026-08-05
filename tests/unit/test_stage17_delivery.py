"""Tests for Stage 17 Power BI delivery semantics."""

import pandas as pd

from cfd.stage17 import _portfolio_overview, _risk_band


def test_risk_band_is_ordered_and_bounded() -> None:
    values = pd.Series([0.0, 0.15, 0.30, 0.50, 1.0])
    assert _risk_band(values).tolist() == ["Low", "Low", "Moderate", "High", "Severe"]


def test_portfolio_overview_reconciles_alerts() -> None:
    watchlist = pd.DataFrame(
        {
            "decision_at": pd.to_datetime(["2024-01-01", "2024-02-01"]),
            "sector": ["Utilities", "Utilities"],
            "cik": ["1", "2"],
            "alert": [True, False],
            "probability": [0.6, 0.2],
            "interest_coverage_ttm": [1.0, 3.0],
            "free_cash_flow_margin_ttm": [0.1, 0.2],
            "total_debt_to_assets": [0.5, 0.4],
            "deterioration_label": [1.0, 0.0],
        }
    )
    result = _portfolio_overview(watchlist)
    assert len(result) == 1
    assert result.loc[0, "monitored_companies"] == 2
    assert result.loc[0, "alerts"] == 1
    assert result.loc[0, "alert_rate"] == 0.5
