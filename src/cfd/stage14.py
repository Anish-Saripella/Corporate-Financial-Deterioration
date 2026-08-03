"""Stage 14 incremental deterioration-classifier experiments."""

from __future__ import annotations

import json
from typing import Any

import duckdb
import pandas as pd

from cfd.config import read_yaml, repository_root
from cfd.modeling.classification import run_temporal_classification


def run_stage_14() -> dict[str, Any]:
    root = repository_root()
    processed = root / "data" / "processed"
    reports = root / "reports" / "generated"
    base = pd.read_parquet(processed / "model_features.parquet")
    forecasts = pd.read_parquet(processed / "forecast_features.parquet")
    assignments = pd.read_parquet(processed / "temporal_split_assignments.parquet")
    features = base.merge(forecasts, on="decision_key", how="left", validate="one_to_one")
    if (
        features["forecast_feature_available_at"].notna()
        & (features["forecast_feature_available_at"] > features["decision_at"])
    ).any():
        raise ValueError("A classifier forecast feature was unavailable at decision time")
    registry = read_yaml(root / "configs" / "feature_registry.yml")
    config = read_yaml(root / "configs" / "modeling.yml")["classification"]
    predictions, metrics = run_temporal_classification(features, assignments, registry, config)
    if predictions.duplicated(["decision_key", "fold_id", "model", "feature_increment"]).any():
        raise ValueError("Duplicate out-of-fold classifier prediction")
    predictions.to_parquet(processed / "classifier_oof_predictions.parquet", index=False)
    features.to_parquet(processed / "model_features_with_forecasts.parquet", index=False)
    partition_root = processed / "partitions" / "classifier_oof_predictions"
    for fold_id, group in predictions.groupby("fold_id"):
        directory = partition_root / f"fold_id={fold_id}"
        directory.mkdir(parents=True, exist_ok=True)
        group.to_parquet(directory / "part.parquet", index=False)
    metrics.to_csv(reports / "classifier_fold_metrics.csv", index=False)
    with duckdb.connect(str(processed / "cfd.duckdb")) as connection:
        for table, filename in {
            "classifier_oof_predictions": "classifier_oof_predictions.parquet",
            "model_features_with_forecasts": "model_features_with_forecasts.parquet",
        }.items():
            location = str(processed / filename).replace("'", "''")
            connection.execute(
                f"CREATE OR REPLACE TABLE marts.{table} AS SELECT * FROM read_parquet('{location}')"
            )
    result = {
        "status": "complete",
        "classification_version": "phase1-modeling-v1",
        "out_of_fold_predictions": len(predictions),
        "unique_validation_decisions": int(predictions["decision_key"].nunique()),
        "models": sorted(predictions["model"].unique().tolist()),
        "feature_increments": sorted(predictions["feature_increment"].unique().tolist()),
        "folds": sorted(predictions["fold_id"].unique().tolist()),
        "locked_holdout_used": False,
    }
    (reports / "stage14_summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result
