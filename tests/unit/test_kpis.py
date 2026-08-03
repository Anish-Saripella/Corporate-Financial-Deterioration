import numpy as np
import pandas as pd

from cfd.features.kpis import free_cash_flow_margin, interest_coverage, total_debt_to_assets


def test_confirmed_kpi_formulas() -> None:
    assert interest_coverage(pd.Series([20.0]), pd.Series([5.0])).iloc[0] == 4.0
    assert (
        free_cash_flow_margin(pd.Series([30.0]), pd.Series([10.0]), pd.Series([100.0])).iloc[0]
        == 0.2
    )
    assert (
        total_debt_to_assets(pd.Series([10.0]), pd.Series([40.0]), pd.Series([100.0])).iloc[0]
        == 0.5
    )


def test_ratio_with_zero_denominator_is_missing() -> None:
    result = interest_coverage(pd.Series([20.0]), pd.Series([0.0]))
    assert np.isnan(result.iloc[0])
