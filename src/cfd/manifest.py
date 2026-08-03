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

    pipeline_version: str = "0.1.0"
    source: str
    url: str
    retrieved_at_utc: datetime
    output_path: str
    sha256: str
    byte_count: int
    parameters: dict[str, Any]


def verify_manifest(path: Path) -> dict[str, Any]:
    """Verify that a manifest's local artifact still matches its recorded checksum."""

    manifest = AcquisitionManifest.model_validate_json(path.read_text(encoding="utf-8"))
    artifact = Path(manifest.output_path)
    if not artifact.exists():
        return {
            "manifest": str(path),
            "artifact": str(artifact),
            "valid": False,
            "reason": "artifact_missing",
        }
    digest = hashlib.sha256()
    byte_count = 0
    with artifact.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
    valid = digest.hexdigest() == manifest.sha256 and byte_count == manifest.byte_count
    return {
        "manifest": str(path),
        "artifact": str(artifact),
        "valid": valid,
        "reason": None if valid else "checksum_or_size_mismatch",
    }


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


def write_existing_file_manifest(
    *,
    path: Path,
    manifest_directory: Path,
    source: str,
    url: str,
    parameters: dict[str, Any] | None = None,
) -> AcquisitionManifest:
    """Create a manifest for a large file downloaded through a streaming client."""

    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
    manifest = AcquisitionManifest(
        source=source,
        url=url,
        retrieved_at_utc=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
        output_path=str(path),
        sha256=digest.hexdigest(),
        byte_count=byte_count,
        parameters=parameters or {},
    )
    manifest_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_directory / f"{path.name}.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
