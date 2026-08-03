import numpy as np
import pandas as pd

from cfd.forecasting.baselines import random_walk_forecast, random_walk_with_drift_forecast


def test_random_walk_baselines() -> None:
    history = pd.Series([1.0, 2.0, 3.0])
    np.testing.assert_array_equal(random_walk_forecast(history, 2), [3.0, 3.0])
    np.testing.assert_array_equal(random_walk_with_drift_forecast(history, 2), [4.0, 5.0])
