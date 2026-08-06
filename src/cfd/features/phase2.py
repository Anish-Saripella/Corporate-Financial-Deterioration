"""Financially motivated, backward-looking features for Phase 2."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    valid_denominator = denominator.where(denominator.abs() > 1e-9)
    return (numerator / valid_denominator).replace([np.inf, -np.inf], np.nan)


def _ensure_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"Phase 2 features require source columns: {missing}")


def engineer_phase2_financial_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Add interpretable debt, liquidity, operating, temporal, and quality signals.

    Every transformation uses information available on the decision row or an
    earlier row for the same company. Winsorization, imputation, and scaling are
    intentionally left to the fold-local model preprocessor.
    """

    required = [
        "cik",
        "decision_at",
        "period_end",
        "sector",
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
        "maximum_source_available_at",
    ]
    _ensure_columns(panel, required)
    result = panel.sort_values(["cik", "decision_at"]).copy()
    result["decision_at"] = pd.to_datetime(result["decision_at"])
    result["period_end"] = pd.to_datetime(result["period_end"])
    grouped = result.groupby("cik", sort=False)

    # Debt structure and near-term refinancing pressure.
    result["short_term_debt_share"] = _safe_ratio(
        result["short_term_debt"], result["total_debt"]
    )
    result["refinancing_gap_to_assets"] = _safe_ratio(
        result["short_term_debt"] - result["cash_and_equivalents"],
        result["total_assets"],
    )
    result["interest_expense_growth_yoy"] = _safe_ratio(
        result["interest_expense_ttm"], grouped["interest_expense_ttm"].shift(4)
    ) - 1

    # Liquidity, internal funding, and capital-investment burden.
    result["working_capital_to_assets"] = _safe_ratio(
        result["current_assets"] - result["current_liabilities"], result["total_assets"]
    )
    result["capital_expenditure_to_revenue"] = _safe_ratio(
        result["capital_expenditures_ttm"], result["revenue_ttm"]
    )
    result["cash_flow_conversion"] = _safe_ratio(
        result["operating_cash_flow_ttm"], result["operating_income_ttm"].abs()
    )

    # Operating performance and asset use.
    result["revenue_growth_yoy"] = _safe_ratio(
        result["revenue_ttm"], grouped["revenue_ttm"].shift(4)
    ) - 1
    result["asset_turnover"] = _safe_ratio(result["revenue_ttm"], result["total_assets"])
    result["net_income_margin_ttm"] = _safe_ratio(
        result["net_income_ttm"], result["revenue_ttm"]
    )

    # Changes and volatility distinguish persistent deterioration from a weak quarter.
    temporal_features = [
        "current_ratio",
        "short_term_debt_share",
        "refinancing_gap_to_assets",
        "revenue_growth_yoy",
        "operating_margin_ttm",
        "asset_turnover",
        "interest_coverage_ttm",
        "free_cash_flow_margin_ttm",
        "total_debt_to_assets",
    ]
    for feature in temporal_features:
        company_feature = result.groupby("cik", sort=False)[feature]
        result[f"{feature}_qoq_change"] = result[feature] - company_feature.shift(1)
        result[f"{feature}_yoy_change_phase2"] = result[feature] - company_feature.shift(4)
        result[f"{feature}_volatility_8q"] = (
            company_feature.rolling(8, min_periods=4).std().reset_index(level=0, drop=True)
        )
        expanding_mean = company_feature.expanding(min_periods=8).mean().reset_index(
            level=0, drop=True
        )
        expanding_std = company_feature.expanding(min_periods=8).std().reset_index(
            level=0, drop=True
        )
        result[f"{feature}_distance_from_history"] = _safe_ratio(
            result[feature] - expanding_mean, expanding_std
        )

    # Peer distance is calculated only among rows available in the same calendar quarter.
    result["calendar_quarter"] = result["decision_at"].dt.to_period("Q").astype(str)
    peer_features = [
        "interest_coverage_ttm",
        "free_cash_flow_margin_ttm",
        "total_debt_to_assets",
        "short_term_debt_share",
        "refinancing_gap_to_assets",
        "working_capital_to_assets",
        "capital_expenditure_to_revenue",
        "revenue_growth_yoy",
        "asset_turnover",
        "net_income_margin_ttm",
    ]
    for feature in peer_features:
        peers = result.groupby(["calendar_quarter", "sector"])[feature]
        result[f"{feature}_sector_percentile"] = peers.rank(pct=True)
        result[f"{feature}_vs_sector_median"] = result[feature] - peers.transform("median")

    # Reporting fields are retained for data-quality monitoring and case review only.
    # They are deliberately excluded from the primary classifier candidate registry.
    result["filing_delay_days"] = (result["decision_at"] - result["period_end"]).dt.days
    result["low_preferred_tag_share"] = 1 - result["preferred_tag_share"]
    result["source_quality_score"] = (
        0.5 * result["preferred_tag_share"]
        + 0.3 * (1 - result["derived_fact_share"])
        + 0.2 * (1 - result["filing_delay_days"].clip(0, 180) / 180)
    )
    if (pd.to_datetime(result["maximum_source_available_at"]) > result["decision_at"]).any():
        raise ValueError("Phase 2 feature input contains future-available financial information")
    return result.sort_index()
