from __future__ import annotations

import pandas as pd

from cfd.labels.deterioration import deterioration_diagnostics


def test_label_diagnostics_records_future_availability_and_episode_start() -> None:
    frame = pd.DataFrame(
        {
            "cik": ["1"] * 7,
            "period_end": pd.date_range("2020-03-31", periods=7, freq="QE"),
            "decision_at": pd.date_range("2020-04-30", periods=7, freq="QE"),
            "fiscal_year": [2020, 2020, 2020, 2020, 2021, 2021, 2021],
            "fiscal_quarter_number": [1, 2, 3, 4, 1, 2, 3],
            "interest_coverage_ttm": [4.0, 3.5, 3.0, 1.4, 1.2, 1.1, 1.0],
        }
    )

    result = deterioration_diagnostics(frame, horizon=4)

    assert result.loc[0, "deterioration_label"] == 1
    assert result.loc[0, "deterioration_episode_start"]
    assert result.loc[0, "label_available_at"] == frame.loc[4, "decision_at"]
    assert pd.isna(result.loc[6, "deterioration_label"])
