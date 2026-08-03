from __future__ import annotations

from pathlib import Path

import pandas as pd

from cfd.local_store import _filter_financial_parquet


def test_filter_financial_parquet_keeps_only_selected_companies(tmp_path: Path) -> None:
    path = tmp_path / "facts.parquet"
    pd.DataFrame(
        {
            "cik": ["1", "1", "2", "3"],
            "value": [10.0, 11.0, 20.0, 30.0],
        }
    ).to_parquet(path, index=False)

    result = _filter_financial_parquet(path, {"0000000001", "0000000003"})
    stored = pd.read_parquet(path)

    assert set(stored["cik"]) == {"0000000001", "0000000003"}
    assert result == {"rows_before": 4, "rows_after": 3, "companies_after": 2}
