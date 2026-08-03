"""Stage 16 production-style orchestration, asset checks, and run manifests."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from cfd.analysis.model_results import run_model_result_plots
from cfd.config import repository_root
from cfd.stage13 import run_stage_13
from cfd.stage14 import run_stage_14
from cfd.stage15 import run_stage_15


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_commit(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def validate_stage_16_artifacts() -> pd.DataFrame:
    root = repository_root()
    processed = root / "data" / "processed"
    checks: list[dict[str, Any]] = []

    def record(asset: str, check: str, passed: bool, evidence: Any) -> None:
        checks.append({"asset": asset, "check": check, "passed": passed, "evidence": evidence})

    forecast = pd.read_parquet(processed / "forecast_backtest_predictions.parquet")
    record("forecast_backtest_predictions", "nonempty", not forecast.empty, len(forecast))
    record(
        "forecast_backtest_predictions",
        "finite_forecasts",
        bool(np.isfinite(forecast["forecast"]).all()),
        int((~np.isfinite(forecast["forecast"])).sum()),
    )
    record(
        "forecast_backtest_predictions",
        "origin_precedes_target",
        bool((forecast["origin_at"] < forecast["target_at"]).all()),
        int((forecast["origin_at"] >= forecast["target_at"]).sum()),
    )
    forecast_features = pd.read_parquet(processed / "forecast_features.parquet")
    record(
        "forecast_features",
        "unique_decision_key",
        not forecast_features["decision_key"].duplicated().any(),
        len(forecast_features),
    )
    oof = pd.read_parquet(processed / "classifier_oof_predictions.parquet")
    oof_key = ["decision_key", "fold_id", "model", "feature_increment"]
    record(
        "classifier_oof_predictions",
        "unique_model_decisions",
        not oof.duplicated(oof_key).any(),
        len(oof),
    )
    record(
        "classifier_oof_predictions",
        "bounded_probabilities",
        bool(oof["probability"].between(0, 1).all()),
        [float(oof["probability"].min()), float(oof["probability"].max())],
    )
    holdout = pd.read_parquet(processed / "final_holdout_predictions.parquet")
    record(
        "final_holdout_predictions",
        "unique_decision_key",
        not holdout["decision_key"].duplicated().any(),
        len(holdout),
    )
    record(
        "final_holdout_predictions",
        "bounded_probabilities",
        bool(holdout["probability"].between(0, 1).all()),
        len(holdout),
    )
    record(
        "champion_classifier",
        "serialized_artifact_exists",
        (root / "artifacts" / "champion_classifier.joblib").is_file(),
        "artifacts/champion_classifier.joblib",
    )
    for stage in ["stage13", "stage14", "stage15"]:
        manifest_path = root / "reports" / "figures" / stage / "figure_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = [root / file for figure in manifest["figures"] for file in figure["files"]]
        record(stage, "figure_manifest_complete", all(path.is_file() for path in files), len(files))
    frame = pd.DataFrame(checks)
    if not frame["passed"].all():
        raise ValueError(
            f"Stage 16 asset checks failed: {frame.loc[~frame['passed']].to_dict('records')}"
        )
    return frame


def finalize_stage_16(
    *,
    stage13: dict[str, Any],
    stage14: dict[str, Any],
    stage15: dict[str, Any],
    plots: dict[str, Any],
    started_at: float,
) -> dict[str, Any]:
    root = repository_root()
    reports = root / "reports" / "generated"
    checks = validate_stage_16_artifacts()
    checks.to_csv(reports / "pipeline_asset_checks.csv", index=False)
    config_files = [
        root / "configs" / name
        for name in [
            "project.yml",
            "analytical_panel.yml",
            "label.yml",
            "feature_registry.yml",
            "temporal_validation.yml",
            "modeling.yml",
            "plot_style.yml",
        ]
    ]
    completed_at = datetime.now(UTC)
    payload = {
        "pipeline_version": "phase1-production-pipeline-v1",
        "run_id": completed_at.strftime("%Y%m%dT%H%M%SZ"),
        "completed_at_utc": completed_at.isoformat(),
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
        "git_commit": _git_commit(root),
        "configuration_sha256": {path.name: _sha256(path) for path in config_files},
        "stage13": stage13,
        "stage14": stage14,
        "stage15": stage15,
        "plots": plots,
        "asset_checks_passed": int(checks["passed"].sum()),
        "asset_checks_failed": int((~checks["passed"]).sum()),
        "network_calls": 0,
        "source_scope": "certified local final-universe store only",
    }
    (reports / "pipeline_run_manifest.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return payload


def run_stages_13_to_16(*, reuse_forecasts: bool = False) -> dict[str, Any]:
    started_at = time.monotonic()
    stage13_path = repository_root() / "reports" / "generated" / "stage13_summary.json"
    if reuse_forecasts:
        if not stage13_path.is_file():
            raise ValueError("Cannot reuse forecasts before a completed Stage 13 run")
        stage13_payload = json.loads(stage13_path.read_text(encoding="utf-8"))
        if not isinstance(stage13_payload, dict):
            raise ValueError("Stage 13 summary is not a JSON object")
        stage13 = stage13_payload
    else:
        stage13 = run_stage_13()
    stage14 = run_stage_14()
    stage15 = run_stage_15()
    plots = run_model_result_plots()
    return finalize_stage_16(
        stage13=stage13,
        stage14=stage14,
        stage15=stage15,
        plots=plots,
        started_at=started_at,
    )
