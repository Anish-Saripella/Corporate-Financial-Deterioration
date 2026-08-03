"""SEC EDGAR client with identification, caching, throttling, and retry behavior."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from cfd.manifest import AcquisitionManifest, write_download_with_manifest

SEC_DATA_BASE = "https://data.sec.gov"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives"


class SecClient:
    """Small SEC client intentionally capped below the published fair-access limit."""

    def __init__(
        self,
        *,
        user_agent: str,
        requests_per_second: float = 5.0,
        timeout_seconds: float = 60.0,
    ) -> None:
        if "@" not in user_agent:
            raise ValueError("SEC User-Agent must contain a contact email")
        if not 0 < requests_per_second <= 5:
            raise ValueError("This project caps SEC traffic at five requests per second")
        self._minimum_interval = 1.0 / requests_per_second
        self._last_request_started = 0.0
        self._client = httpx.Client(
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
            timeout=timeout_seconds,
            follow_redirects=True,
        )

    def __enter__(self) -> SecClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_started
        if elapsed < self._minimum_interval:
            time.sleep(self._minimum_interval - elapsed)
        self._last_request_started = time.monotonic()

    def get_bytes(self, url: str, *, attempts: int = 4) -> bytes:
        """Fetch bytes with bounded exponential backoff for transient responses."""

        for attempt in range(attempts):
            self._throttle()
            response = self._client.get(url)
            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()
                return response.content
            if attempt == attempts - 1:
                response.raise_for_status()
            time.sleep(2**attempt)
        raise RuntimeError("unreachable retry state")

    def download(
        self,
        *,
        url: str,
        destination: Path,
        manifest_directory: Path,
        parameters: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> AcquisitionManifest:
        """Download once by default; every write receives a checksum manifest."""

        if destination.exists() and not overwrite:
            raise FileExistsError(f"Refusing to overwrite cached SEC data: {destination}")
        content = self.get_bytes(url)
        return write_download_with_manifest(
            content=content,
            destination=destination,
            manifest_directory=manifest_directory,
            source="SEC EDGAR",
            url=url,
            parameters=parameters,
        )

    def submissions_url(self, cik: int | str) -> str:
        normalized = str(cik).zfill(10)
        if not normalized.isdigit() or len(normalized) != 10:
            raise ValueError(f"Invalid CIK: {cik}")
        return f"{SEC_DATA_BASE}/submissions/CIK{normalized}.json"

    def companyfacts_url(self, cik: int | str) -> str:
        normalized = str(cik).zfill(10)
        if not normalized.isdigit() or len(normalized) != 10:
            raise ValueError(f"Invalid CIK: {cik}")
        return f"{SEC_DATA_BASE}/api/xbrl/companyfacts/CIK{normalized}.json"
