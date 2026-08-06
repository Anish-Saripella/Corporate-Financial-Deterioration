from __future__ import annotations

import pandas as pd

from cfd.stage26 import build_recall_first_policy_table


def test_recall_first_policy_meets_each_sector_target_with_distinct_thresholds() -> None:
    predictions = pd.DataFrame(
        {
            "sector": ["Consumer Discretionary"] * 5 + ["Utilities"] * 5,
            "deterioration_label": [1, 1, 0, 0, 0, 1, 1, 0, 0, 0],
            "probability": [0.9, 0.6, 0.5, 0.2, 0.1, 0.8, 0.4, 0.7, 0.3, 0.1],
        }
    )
    table = build_recall_first_policy_table(predictions, [0.8])
    row = table.iloc[0]
    assert row["consumer_recall"] >= 0.8
    assert row["utility_recall"] >= 0.8
    assert row["consumer_threshold"] != row["utility_threshold"]
