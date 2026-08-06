"""Stage 22: materialize Phase 2 development-only analytical evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from cfd.config import read_yaml, repository_root
from cfd.phase2.analysis import development_evidence


def run_stage_22(predictions_path: Path | None = None) -> dict[str, Any]:
    """Analyze real OOF predictions; this stage never evaluates a final test set."""

    root = repository_root()
    source = predictions_path or root / "data" / "processed" / "phase2_oof_predictions.parquet"
    if not source.exists():
        raise FileNotFoundError(f"Real Phase 2 out-of-fold predictions not found at {source}")
    predictions = pd.read_parquet(source)
    config = read_yaml(root / "configs" / "phase2.yml")
    tables = development_evidence(predictions, config)
    reports = root / "reports" / "generated"
    for name, table in tables.items():
        table.to_csv(reports / f"phase2_{name}.csv", index=False)
    summary = {
        "status": "complete",
        "analysis_type": "development_out_of_fold_only",
        "models": sorted(predictions["model"].unique().tolist()),
        "company_quarters": int(predictions["decision_key"].nunique()),
        "issuers": int(predictions["cik"].nunique()),
        "tables": {name: len(table) for name, table in tables.items()},
        "final_test_evaluated": False,
        "synthetic_data_used": False,
    }
    (reports / "stage22_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary
