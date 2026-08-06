"""Stage 19: audit real-data readiness for Phase 2 development and testing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from cfd.config import read_yaml, repository_root
from cfd.phase2.readiness import audit_phase2_readiness


def run_stage_19(panel_path: Path | None = None) -> dict[str, Any]:
    """Audit the real panel; never generate or substitute analytical rows."""

    root = repository_root()
    source = panel_path or root / "data" / "processed" / "phase2_model_features.parquet"
    if not source.exists():
        raise FileNotFoundError(
            f"Real Phase 2 panel not found at {source}. Run real-source ingestion and panel "
            "construction first; synthetic substitution is prohibited."
        )
    panel = pd.read_parquet(source)
    config = read_yaml(root / "configs" / "phase2.yml")
    result = audit_phase2_readiness(panel, config)
    reports = root / "reports" / "generated"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "phase2_readiness.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    pd.DataFrame(result["sector_evidence"]).to_csv(
        reports / "phase2_sector_readiness.csv", index=False
    )
    return result
