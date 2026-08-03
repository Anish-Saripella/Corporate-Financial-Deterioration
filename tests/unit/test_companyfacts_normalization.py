from datetime import date

import pandas as pd

from cfd.normalization.companyfacts import normalize_fiscal_quarters


def test_normalization_never_collapses_different_companies() -> None:
    frame = pd.DataFrame(
        {
            "cik": ["0000000001", "0000000002"],
            "entity_name": ["One", "Two"],
            "concept": ["total_assets", "total_assets"],
            "taxonomy_tag": ["Assets", "Assets"],
            "tag_priority": [0, 0],
            "statement": ["balance_sheet", "balance_sheet"],
            "period_type": ["instant", "instant"],
            "unit": ["USD", "USD"],
            "start_date": [pd.NaT, pd.NaT],
            "end_date": pd.to_datetime(["2023-03-31", "2023-03-31"]),
            "value": [100.0, 200.0],
            "accession_number": ["one", "two"],
            "fiscal_year": pd.Series([2023, 2023], dtype="Int64"),
            "fiscal_period": ["Q1", "Q1"],
            "form": ["10-Q", "10-Q"],
            "filed_at": pd.to_datetime(["2023-05-01", "2023-05-02"]),
            "frame": [None, None],
            "duration_days": [float("nan"), float("nan")],
        }
    )
    result = normalize_fiscal_quarters(frame, cutoff=date(2025, 12, 31))
    assert result[["cik", "value"]].to_dict("records") == [
        {"cik": "0000000001", "value": 100.0},
        {"cik": "0000000002", "value": 200.0},
    ]
