import pandas as pd
import pytest

from cfd.normalization.fiscal import derive_fourth_quarter, validate_fiscal_index


def test_derive_fourth_quarter_duration_value() -> None:
    assert derive_fourth_quarter(100.0, 20.0, 25.0, 30.0) == 25.0


def test_fiscal_standardization_keeps_real_dates_and_filing_provenance() -> None:
    frame = pd.DataFrame(
        {
            "cik": [1],
            "fiscal_year": [2024],
            "fiscal_quarter": ["FQ1"],
            "period_end": ["2024-03-31"],
            "filed_at": ["2024-05-07"],
            "accession_number": ["0000000001-24-000001"],
        }
    )
    validate_fiscal_index(frame)


def test_filing_before_period_end_is_rejected() -> None:
    frame = pd.DataFrame(
        {
            "cik": [1],
            "fiscal_year": [2024],
            "fiscal_quarter": ["FQ1"],
            "period_end": ["2024-03-31"],
            "filed_at": ["2024-03-01"],
            "accession_number": ["x"],
        }
    )
    with pytest.raises(ValueError, match="cannot be available"):
        validate_fiscal_index(frame)
