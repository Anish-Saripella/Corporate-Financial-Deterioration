from __future__ import annotations

import pandas as pd

from cfd.labels.phase2 import (
    label_sensitivity_summary,
    make_multikpi_deterioration_label,
    registered_coverage_labels,
)


def _config() -> dict:
    return {
        "label_sensitivity": {
            "benchmark": {
                "horizon_quarters": 4,
                "coverage_multiple": 1.5,
                "relative_coverage_decline": 0.40,
            },
            "registered_horizons_quarters": [2, 4, 6],
            "registered_coverage_multiples": [1.0, 1.5, 2.0],
            "multi_kpi_rule": {
                "components_required": 2,
                "negative_fcf_margin_threshold": 0.0,
                "leverage_increase_threshold": 0.10,
            },
        }
    }


def _panel() -> pd.DataFrame:
    dates = pd.date_range("2020-03-31", periods=9, freq="QE")
    return pd.DataFrame(
        {
            "cik": ["1"] * 9,
            "period_end": dates,
            "decision_at": dates + pd.Timedelta(45, unit="D"),
            "sector": ["Utilities"] * 9,
            "interest_coverage_ttm": [4.0, 4.0, 4.0, 4.0, 1.0, 0.8, 0.7, 0.6, 0.5],
            "free_cash_flow_margin_ttm": [0.1, 0.1, 0.1, 0.1, -0.1, -0.2, -0.1, 0, 0],
            "total_debt_to_assets": [0.3, 0.3, 0.3, 0.3, 0.45, 0.5, 0.5, 0.5, 0.5],
        }
    )


def test_all_preregistered_coverage_variants_are_generated() -> None:
    labels = registered_coverage_labels(_panel(), _config())
    assert len(labels) == 9
    assert "coverage_h4_threshold_1.5" in labels


def test_multikpi_label_requires_two_components_and_summary_counts_episodes() -> None:
    panel = _panel()
    label = make_multikpi_deterioration_label(panel, _config())
    assert label.dropna().sum() >= 1
    summary = label_sensitivity_summary(panel, _config())
    assert len(summary) == 20
    assert not summary["selected_using_model_performance"].any()
