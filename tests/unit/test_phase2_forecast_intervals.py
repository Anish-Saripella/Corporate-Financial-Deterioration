import numpy as np
import pandas as pd

from cfd.forecasting.intervals import apply_empirical_intervals, fit_empirical_intervals


def test_empirical_intervals_use_sector_width_when_sample_is_sufficient() -> None:
    frame = pd.DataFrame(
        {
            "kpi": ["coverage"] * 80,
            "sector": ["Utilities"] * 40 + ["Consumer Discretionary"] * 40,
            "horizon": [4] * 80,
            "actual": np.r_[np.arange(40), np.arange(40)],
            "forecast": np.r_[np.arange(40) + 1, np.arange(40) + 3],
        }
    )
    calibration = fit_empirical_intervals(
        frame, interval_level=0.95, minimum_group_observations=30
    )
    assert set(calibration["calibration_scope"]) == {"sector_kpi_horizon"}
    widths = calibration.set_index("sector")["absolute_residual_quantile"]
    assert widths["Utilities"] == 1
    assert widths["Consumer Discretionary"] == 3
    applied = apply_empirical_intervals(frame.head(1), calibration)
    assert applied.iloc[0]["lower_interval"] == applied.iloc[0]["forecast"] - 1


def test_small_sector_group_uses_pooled_fallback() -> None:
    frame = pd.DataFrame(
        {
            "kpi": ["leverage"] * 12,
            "sector": ["Utilities"] * 2 + ["Consumer Discretionary"] * 10,
            "horizon": [1] * 12,
            "actual": np.arange(12, dtype=float),
            "forecast": np.arange(12, dtype=float) + 1,
        }
    )
    calibration = fit_empirical_intervals(
        frame, interval_level=0.90, minimum_group_observations=5
    )
    utility = calibration.loc[calibration["sector"] == "Utilities"].iloc[0]
    assert utility["calibration_scope"] == "pooled_kpi_horizon_fallback"
    assert utility["calibration_observations"] == 12
