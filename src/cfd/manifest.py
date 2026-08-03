"""Acquisition manifests for reproducible, auditable source downloads."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict


class AcquisitionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    url: str
    retrieved_at_utc: datetime
    output_path: str
    sha256: str
    byte_count: int
    parameters: dict[str, Any]


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def write_download_with_manifest(
    *,
    content: bytes,
    destination: Path,
    manifest_directory: Path,
    source: str,
    url: str,
    parameters: dict[str, Any] | None = None,
) -> AcquisitionManifest:
    """Persist a response and an adjacent immutable-style acquisition record."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest_directory.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    manifest = AcquisitionManifest(
        source=source,
        url=url,
        retrieved_at_utc=datetime.now(UTC),
        output_path=str(destination),
        sha256=sha256_bytes(content),
        byte_count=len(content),
        parameters=parameters or {},
    )
    manifest_path = manifest_directory / f"{destination.name}.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
