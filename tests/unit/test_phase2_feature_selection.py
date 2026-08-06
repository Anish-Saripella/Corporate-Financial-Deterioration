from __future__ import annotations

import numpy as np
import pandas as pd

from cfd.modeling.feature_selection import select_features_temporally


def test_feature_selection_never_uses_outer_validation_outcomes() -> None:
    dates = pd.date_range("2014-03-31", periods=36, freq="QE")
    rows = []
    for company in range(6):
        for position, date in enumerate(dates):
            label = int(position % 4 == 0)
            rows.append(
                {
                    "decision_key": f"{company}|{date.date()}",
                    "cik": str(company),
                    "decision_at": date,
                    "label_available_at": date + pd.offsets.QuarterEnd(4),
                    "sector": "Utilities" if company >= 3 else "Consumer Discretionary",
                    "industry": "A" if company % 2 else "B",
                    "deterioration_label": label,
                    "interest_coverage_ttm": float(label) + company * 0.001,
                    "noise": float((position * 17 + company) % 11),
                }
            )
    features = pd.DataFrame(rows)
    assignments = features[["decision_key", "cik", "decision_at"]].copy()
    assignments["fold_id"] = "fold_01"
    assignments["split"] = np.where(
        assignments["decision_at"].isin(dates[-4:]), "VALIDATION", "TRAIN"
    )
    config = {
        "minimum_inner_training_quarters": 12,
        "inner_validation_window_quarters": 4,
        "inner_validation_windows": 2,
        "feature_selection": {
            "protected_core_features": ["interest_coverage_ttm"],
            "maximum_missing_rate": 0.60,
            "maximum_absolute_correlation": 0.92,
            "permutation_repeats": 2,
            "minimum_positive_window_share": 0.50,
            "minimum_features": 1,
            "maximum_features": 2,
            "random_seed": 42,
        },
    }
    selected, evidence = select_features_temporally(
        features, assignments, ["interest_coverage_ttm", "noise"], config
    )
    assert "interest_coverage_ttm" in selected["fold_01"]
    assert not evidence["outer_validation_used_for_selection"].any()
