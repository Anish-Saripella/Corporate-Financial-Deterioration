import pandas as pd

from cfd.labels.deterioration import make_deterioration_label


def test_deterioration_requires_absolute_and_relative_conditions() -> None:
    frame = pd.DataFrame(
        {
            "cik": [1] * 5 + [2] * 5,
            "period_end": pd.date_range("2023-03-31", periods=5, freq="QE").tolist() * 2,
            "interest_coverage_ttm": [4.0, 3.0, 2.0, 1.4, 1.2, 2.0, 1.9, 1.8, 1.7, 1.6],
        }
    )
    labels = make_deterioration_label(frame)
    assert labels.iloc[0] == 1
    assert labels.iloc[5] == 0
    assert labels.iloc[1:].isna().sum() == 8
