from __future__ import annotations

import pandas as pd

from cfd.phase2.readiness import audit_phase2_readiness


def test_readiness_does_not_treat_phase1_sized_panel_as_phase2_ready() -> None:
    panel = pd.DataFrame(
        {
            "cik": ["1", "1", "2", "2"],
            "sector": ["Utilities"] * 4,
            "decision_at": pd.date_range("2020-03-31", periods=4, freq="QE"),
            "deterioration_label": [0, 1, 0, 1],
        }
    )
    config = {
        "version": "test",
        "evaluation_policy": {
            "consumed_benchmark_start": "2023-01-01",
            "untouched_test_start": None,
            "minimum_issuers_per_sector": 75,
            "minimum_episodes_per_sector": 150,
        },
    }
    result = audit_phase2_readiness(panel, config)
    assert result["status"] == "not_ready"
    assert result["final_test_may_be_opened"] is False
    assert result["gates"]["new_untouched_test_boundary_registered"] is False


def test_readiness_ignores_immature_labels_when_counting_episodes() -> None:
    panel = pd.DataFrame(
        {
            "cik": ["1", "1", "1"],
            "sector": ["Utilities"] * 3,
            "decision_at": pd.date_range("2020-03-31", periods=3, freq="QE"),
            "deterioration_label": pd.Series([0, 1, pd.NA], dtype="Int8"),
        }
    )
    config = {
        "version": "test",
        "evaluation_policy": {
            "consumed_benchmark_start": "2023-01-01",
            "untouched_test_start": None,
            "minimum_issuers_per_sector": 1,
            "minimum_episodes_per_sector": 1,
        },
    }
    result = audit_phase2_readiness(panel, config)
    assert result["sector_evidence"][0]["episodes"] == 1
