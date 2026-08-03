"""FRED/ALFRED observations client with explicit vintage parameters."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from cfd.manifest import AcquisitionManifest, write_download_with_manifest

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"


class FredClient:
    def __init__(self, *, api_key: str, timeout_seconds: float = 60.0) -> None:
        if not api_key:
            raise ValueError("A FRED API key is required")
        self._api_key = api_key
        self._client = httpx.Client(timeout=timeout_seconds, follow_redirects=True)

    def __enter__(self) -> FredClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def observations(
        self,
        *,
        series_id: str,
        realtime_start: str = "2012-01-01",
        realtime_end: str | None = None,
        output_type: int = 1,
        observation_start: str = "2012-01-01",
    ) -> tuple[bytes, dict[str, Any]]:
        """Retrieve observations while retaining their real-time availability periods."""

        effective_realtime_end = realtime_end or date.today().isoformat()
        parameters: dict[str, Any] = {
            "series_id": series_id,
            "api_key": self._api_key,
            "file_type": "json",
            "realtime_start": realtime_start,
            "realtime_end": effective_realtime_end,
            "output_type": output_type,
            "observation_start": observation_start,
        }
        response = self._client.get(FRED_OBSERVATIONS_URL, params=parameters)
        response.raise_for_status()
        payload = response.json()
        if "observations" not in payload:
            raise ValueError(
                f"Unexpected FRED response for {series_id}: {json.dumps(payload)[:200]}"
            )
        safe_parameters = {key: value for key, value in parameters.items() if key != "api_key"}
        return response.content, safe_parameters

    def download_observations(
        self,
        *,
        series_id: str,
        destination: Path,
        manifest_directory: Path,
        realtime_start: str = "2012-01-01",
        realtime_end: str | None = None,
        output_type: int = 1,
        observation_start: str = "2012-01-01",
    ) -> AcquisitionManifest:
        content, parameters = self.observations(
            series_id=series_id,
            realtime_start=realtime_start,
            realtime_end=realtime_end,
            output_type=output_type,
            observation_start=observation_start,
        )
        return write_download_with_manifest(
            content=content,
            destination=destination,
            manifest_directory=manifest_directory,
            source="FRED/ALFRED",
            url=FRED_OBSERVATIONS_URL,
            parameters=parameters,
        )
