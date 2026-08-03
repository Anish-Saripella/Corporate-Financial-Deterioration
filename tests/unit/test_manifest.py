from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from cfd.manifest import AcquisitionManifest, sha256_bytes, verify_manifest


def _write_manifest(tmp_path: Path, artifact: Path, content: bytes) -> Path:
    manifest = AcquisitionManifest(
        source="test",
        url="https://example.test/source",
        retrieved_at_utc=datetime.now(UTC),
        output_path=str(artifact),
        sha256=sha256_bytes(content),
        byte_count=len(content),
        parameters={},
    )
    path = tmp_path / "source.manifest.json"
    path.write_text(json.dumps(manifest.model_dump(mode="json")), encoding="utf-8")
    return path


def test_verify_manifest_accepts_unchanged_artifact(tmp_path: Path) -> None:
    content = b"source data"
    artifact = tmp_path / "source.bin"
    artifact.write_bytes(content)
    manifest = _write_manifest(tmp_path, artifact, content)

    assert verify_manifest(manifest)["valid"] is True


def test_verify_manifest_rejects_changed_artifact(tmp_path: Path) -> None:
    content = b"source data"
    artifact = tmp_path / "source.bin"
    artifact.write_bytes(content)
    manifest = _write_manifest(tmp_path, artifact, content)
    artifact.write_bytes(b"changed")

    result = verify_manifest(manifest)
    assert result["valid"] is False
    assert result["reason"] == "checksum_or_size_mismatch"
