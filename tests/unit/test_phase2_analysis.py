from __future__ import annotations

import pandas as pd

from cfd.phase2.analysis import development_evidence


def test_development_evidence_keeps_operating_and_statistical_views_separate() -> None:
    rows = []
    dates = pd.date_range("2020-03-31", periods=8, freq="QE")
    for company_number in range(4):
        for index, date in enumerate(dates):
            label = int(index in {3, 4})
            rows.append(
                {
                    "decision_key": f"{company_number}|{date.date()}",
                    "cik": str(company_number),
                    "decision_at": date,
                    "sector": ("Utilities" if company_number % 2 else "Consumer Discretionary"),
                    "deterioration_label": label,
                    "model": "logistic",
                    "probability": 0.8 if label else 0.1,
                    "fold_id": "fold_01",
                    "threshold": 0.5,
                }
            )
    config = {
        "decision_policy": {
            "review_fractions": [0.10, 0.20],
            "missed_event_cost": 5,
            "unnecessary_review_cost": 1,
            "correct_alert_benefit": 1,
            "maximum_alert_rate": 0.20,
        },
        "uncertainty": {
            "cluster_column": "cik",
            "bootstrap_repetitions": 20,
            "confidence_level": 0.95,
            "random_seed": 3,
        },
    }
    tables = development_evidence(pd.DataFrame(rows), config)
    assert set(tables) == {
        "metrics",
        "review_queues",
        "episode_capture",
        "clustered_uncertainty",
        "decision_value",
        "calibration_decomposition",
    }
    assert set(tables["metrics"]["slice"]) == {
        "Overall",
        "Consumer Discretionary",
        "Utilities",
    }
