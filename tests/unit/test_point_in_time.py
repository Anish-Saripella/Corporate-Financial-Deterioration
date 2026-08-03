import pandas as pd

from cfd.features.point_in_time import asof_join


def test_asof_join_never_uses_future_filing() -> None:
    decisions = pd.DataFrame(
        {
            "cik": [1, 1],
            "decision_at": ["2024-05-01", "2024-05-15"],
        }
    )
    observations = pd.DataFrame(
        {
            "cik": [1, 1],
            "period_end": ["2023-12-31", "2024-03-31"],
            "available_at": ["2024-02-20", "2024-05-07"],
            "revenue": [100.0, 110.0],
        }
    )
    result = asof_join(decisions, observations, by="cik")
    assert result["revenue"].tolist() == [100.0, 110.0]
    assert (result["available_at"] <= result["decision_at"]).all()
