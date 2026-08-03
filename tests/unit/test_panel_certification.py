from __future__ import annotations

import pandas as pd

from cfd.panel import KPI_COLUMNS, certify_panel


def test_certification_requires_every_kpi_to_pass() -> None:
    rows = 28
    frame = pd.DataFrame(
        {
            "cik": ["1"] * rows,
            "company_name": ["Example"] * rows,
            "ticker": ["EX"] * rows,
            "sector": ["Utilities"] * rows,
            "fiscal_year": [2015 + index // 4 for index in range(rows)],
            "fiscal_quarter_number": [index % 4 + 1 for index in range(rows)],
            "decision_key": [f"1|{index}" for index in range(rows)],
            "decision_at": pd.date_range("2015-03-31", periods=rows, freq="QE"),
            "maximum_source_available_at": pd.date_range("2015-03-30", periods=rows, freq="QE"),
            "macro_available_at_max": pd.date_range("2015-03-30", periods=rows, freq="QE"),
            "accession_numbers_json": ["[]"] * rows,
            KPI_COLUMNS[0]: [2.0] * rows,
            KPI_COLUMNS[1]: [0.1] * 10 + [None] * 18,
            KPI_COLUMNS[2]: [0.4] * rows,
        }
    )

    _, summary = certify_panel(frame, universe_version="test")

    assert not summary.loc[0, "certified"]
    assert "FREE_CASH_FLOW" in summary.loc[0, "failed_rules"]
