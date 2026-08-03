import pytest

from cfd.ingestion.sec import SecClient


def test_sec_client_validates_identity_and_rate() -> None:
    with pytest.raises(ValueError, match="contact email"):
        SecClient(user_agent="anonymous")
    with pytest.raises(ValueError, match="five requests"):
        SecClient(user_agent="Person person@example.com", requests_per_second=6)


def test_sec_urls_normalize_cik() -> None:
    with SecClient(user_agent="Person person@example.com") as client:
        assert client.submissions_url(320193).endswith("CIK0000320193.json")
        assert client.companyfacts_url("320193").endswith("CIK0000320193.json")
