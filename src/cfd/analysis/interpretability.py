"""Plain-language, non-causal company risk explanations for Phase 2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ReasonRule:
    feature: str
    direction: str
    label: str
    financial_meaning: str


REASON_RULES = (
    ReasonRule(
        "interest_coverage_ttm_sector_percentile",
        "low",
        "Weak debt-service capacity versus sector peers",
        "Lower operating earnings relative to interest expense leaves less protection for lenders.",
    ),
    ReasonRule(
        "interest_coverage_ttm_yoy_change",
        "low",
        "Interest coverage is deteriorating",
        "Coverage fell from the comparable quarter a year earlier.",
    ),
    ReasonRule(
        "free_cash_flow_margin_ttm_sector_percentile",
        "low",
        "Weak free cash flow versus sector peers",
        "Less cash remains after operating and capital-investment needs.",
    ),
    ReasonRule(
        "total_debt_to_assets_sector_percentile",
        "high",
        "High leverage versus sector peers",
        "A larger share of assets is financed by debt, increasing refinancing sensitivity.",
    ),
    ReasonRule(
        "total_debt_to_assets_yoy_change",
        "high",
        "Leverage is rising",
        "Debt relative to assets increased from the comparable quarter a year earlier.",
    ),
    ReasonRule(
        "BAA10Y",
        "high",
        "Corporate financing conditions are tight",
        "The corporate-to-Treasury yield spread is elevated, a proxy for refinancing pressure.",
    ),
    ReasonRule(
        "forecast_interest_coverage_uncertainty_4q",
        "high",
        "The coverage forecast is unusually uncertain",
        "A wide forecast range reduces confidence in the four-quarter central estimate.",
    ),
    ReasonRule(
        "filing_delay_days",
        "high",
        "Financial reporting was slower than usual",
        "Reporting delay is a data-quality association, not direct evidence of financial stress.",
    ),
)


def company_reason_codes(
    row: pd.Series,
    reference: pd.DataFrame,
    *,
    maximum_reasons: int = 4,
) -> list[dict[str, Any]]:
    """Return economically motivated reasons using development-data percentiles.

    This explains which observed conditions are unusual; it does not claim that
    changing a feature would cause the predicted risk to change.
    """

    reasons: list[dict[str, Any]] = []
    for rule in REASON_RULES:
        if rule.feature not in row or rule.feature not in reference:
            continue
        value = row[rule.feature]
        history = reference[rule.feature].dropna()
        if pd.isna(value) or len(history) < 5:
            continue
        percentile = float((history <= value).mean())
        severity = 1 - percentile if rule.direction == "low" else percentile
        if severity < 0.75:
            continue
        reasons.append(
            {
                "feature": rule.feature,
                "label": rule.label,
                "financial_meaning": rule.financial_meaning,
                "value": float(value),
                "development_percentile": percentile,
                "severity": severity,
                "interpretation": "predictive association, not a causal claim",
            }
        )
    return sorted(reasons, key=lambda item: item["severity"], reverse=True)[:maximum_reasons]


def build_company_explanations(
    scored: pd.DataFrame,
    development_reference: pd.DataFrame,
    *,
    maximum_reasons: int = 4,
) -> pd.DataFrame:
    """Attach compact reason codes and plain-language limitations to scored rows."""

    required = {"cik", "decision_at", "probability"}
    missing = required - set(scored.columns)
    if missing:
        raise ValueError(f"Scored rows are missing explanation columns: {sorted(missing)}")
    rows: list[dict[str, Any]] = []
    for _, row in scored.iterrows():
        reasons = company_reason_codes(row, development_reference, maximum_reasons=maximum_reasons)
        probability = float(row["probability"])
        risk_band = "High" if probability >= 0.67 else "Medium" if probability >= 0.33 else "Low"
        rows.append(
            {
                "cik": row["cik"],
                "decision_at": row["decision_at"],
                "probability": probability,
                "risk_band": risk_band,
                "reason_count": len(reasons),
                "reason_codes_json": json.dumps(reasons),
                "interpretation_limit": (
                    "Reasons describe predictive associations and unusual observed conditions; "
                    "they do not identify causes or prescribe management actions."
                ),
            }
        )
    return pd.DataFrame(rows)
