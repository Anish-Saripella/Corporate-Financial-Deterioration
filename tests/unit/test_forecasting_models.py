import numpy as np
import pandas as pd

from cfd.forecasting.models import forecast_series


def test_forecast_candidates_return_finite_four_step_results() -> None:
    history = pd.Series(np.linspace(1.0, 3.0, 24) + np.sin(np.arange(24)) * 0.1)
    exog = pd.DataFrame(
        {"DFF": np.linspace(0, 4, 24), "BAA10Y": np.linspace(2, 3, 24), "UNRATE": 4.0}
    )
    for model in [
        "random_walk",
        "random_walk_drift",
        "local_level",
        "local_linear_trend",
        "regression_dlm",
    ]:
        result = forecast_series(history, model_name=model, horizon=4, exog_history=exog)
        assert len(result.mean) == 4
        assert np.isfinite(result.mean).all()
        assert (result.lower <= result.upper).all()
