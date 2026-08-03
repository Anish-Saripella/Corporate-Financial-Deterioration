from __future__ import annotations

import numpy as np
import pandas as pd

from cfd.features.engineering import TrainingQuantileClipper, engineer_historical_features


def _feature_fixture() -> pd.DataFrame:
    rows = 8
    return pd.DataFrame(
        {
            "cik": ["1"] * rows,
            "decision_key": [f"1|{index}" for index in range(rows)],
            "decision_at": pd.date_range("2020-01-01", periods=rows, freq="QE"),
            "maximum_source_available_at": pd.date_range("2019-12-31", periods=rows, freq="QE"),
            "macro_available_at_max": pd.date_range("2019-12-31", periods=rows, freq="QE"),
            "sector": ["Utilities"] * rows,
            "interest_coverage_ttm": np.arange(1.0, 9.0),
            "free_cash_flow_margin_ttm": np.arange(1.0, 9.0) / 10,
            "total_debt_to_assets": np.arange(1.0, 9.0) / 20,
            "INDPRO": np.arange(100.0, 108.0),
            "RSAFS": np.arange(200.0, 208.0),
            "deterioration_label": [0] * rows,
        }
    )


def test_historical_features_use_only_current_and_past_rows() -> None:
    original = _feature_fixture()
    changed_future = original.copy()
    changed_future.loc[7, "interest_coverage_ttm"] = 999.0

    baseline = engineer_historical_features(original)
    changed = engineer_historical_features(changed_future)

    historical_columns = [
        "interest_coverage_ttm_lag1",
        "interest_coverage_ttm_yoy_change",
        "interest_coverage_ttm_trend_4q",
    ]
    pd.testing.assert_frame_equal(
        baseline.loc[:6, historical_columns], changed.loc[:6, historical_columns]
    )


def test_quantile_clipper_keeps_training_bounds_when_transforming() -> None:
    clipper = TrainingQuantileClipper(lower=0.0, upper=1.0).fit([[0.0], [10.0]])
    transformed = clipper.transform([[100.0]])

    assert transformed[0, 0] == 10.0
