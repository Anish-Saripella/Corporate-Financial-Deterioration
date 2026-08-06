"""Tests for the paired Phase 2 horizon sensitivity analysis."""

import pandas as pd

from cfd.stage28 import _first_breach_lead


def test_first_breach_lead_reports_earliest_qualifying_quarter() -> None:
    frame = pd.DataFrame(
        {
            "cik": ["1"] * 5,
            "period_end": pd.to_datetime(
                ["2020-03-31", "2020-06-30", "2020-09-30", "2020-12-31", "2021-03-31"]
            ),
            "interest_coverage_ttm": [4.0, 3.0, 1.4, 1.0, 0.5],
        }
    )

    lead = _first_breach_lead(frame, horizon=4)

    assert lead.iloc[0] == 2


def test_two_quarter_lead_does_not_look_beyond_its_window() -> None:
    frame = pd.DataFrame(
        {
            "cik": ["1"] * 4,
            "period_end": pd.to_datetime(["2020-03-31", "2020-06-30", "2020-09-30", "2020-12-31"]),
            "interest_coverage_ttm": [4.0, 3.5, 3.0, 1.0],
        }
    )

    lead = _first_breach_lead(frame, horizon=2)

    assert pd.isna(lead.iloc[0])
