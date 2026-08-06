import pandas as pd

from cfd.analysis.interpretability import build_company_explanations, company_reason_codes


def test_reason_codes_use_reference_distribution_and_noncausal_wording() -> None:
    reference = pd.DataFrame(
        {
            "interest_coverage_ttm_sector_percentile": [0.1, 0.2, 0.3, 0.5, 0.7, 0.9],
            "total_debt_to_assets_yoy_change": [-0.1, 0.0, 0.01, 0.02, 0.04, 0.08],
        }
    )
    row = pd.Series(
        {
            "interest_coverage_ttm_sector_percentile": 0.05,
            "total_debt_to_assets_yoy_change": 0.10,
        }
    )
    reasons = company_reason_codes(row, reference)
    assert len(reasons) == 2
    assert all("not a causal claim" in reason["interpretation"] for reason in reasons)


def test_company_explanation_separates_risk_band_from_causal_claims() -> None:
    reference = pd.DataFrame(
        {"filing_delay_days": [20, 25, 30, 35, 40, 45], "probability": [0.1] * 6}
    )
    scored = pd.DataFrame(
        {
            "cik": ["1"],
            "decision_at": [pd.Timestamp("2025-01-01")],
            "probability": [0.75],
            "filing_delay_days": [90],
        }
    )
    result = build_company_explanations(scored, reference)
    assert result.iloc[0]["risk_band"] == "High"
    assert "do not identify causes" in result.iloc[0]["interpretation_limit"]
