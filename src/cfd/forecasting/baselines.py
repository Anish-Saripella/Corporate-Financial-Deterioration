"""Required naïve forecasting benchmarks."""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import NDArray


def random_walk_forecast(history: pd.Series, horizon: int) -> NDArray[np.float64]:
    clean = history.dropna().astype(float)
    if clean.empty or horizon < 1:
        raise ValueError("A nonempty history and positive horizon are required")
    return np.repeat(clean.iloc[-1], horizon)


def random_walk_with_drift_forecast(history: pd.Series, horizon: int) -> NDArray[np.float64]:
    clean = history.dropna().astype(float)
    if len(clean) < 2 or horizon < 1:
        raise ValueError("At least two observations and a positive horizon are required")
    drift = (clean.iloc[-1] - clean.iloc[0]) / (len(clean) - 1)
    return np.asarray(clean.iloc[-1] + drift * np.arange(1, horizon + 1), dtype=np.float64)
