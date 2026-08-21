"""Stage 29: run Phase 3 development models and freeze development evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.metrics import (  # type: ignore[import-untyped]
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from cfd.config import read_yaml, repository_root
from cfd.modeling.phase3 import run_phase3_development


def _candidate_features(root: Path, config: dict[str, Any]) -> list[str]:
    registry = read_yaml(root / "configs" / "phase2_feature_registry.yml")
    registered = [feature for group in registry["candidate_features"].values() for feature in group]
    return [*registered, *config["features"].get("additional_candidates", [])]


def latest_prediction_per_decision(predictions: pd.DataFrame) -> pd.DataFrame:
    """Use the model trained closest to, but not after, each decision."""

    ordered = predictions.sort_values(["decision_key", "model", "origin"])
    return ordered.drop_duplicates(["decision_key", "model"], keep="last").reset_index(drop=True)


def _threshold_at_recall(group: pd.DataFrame, target: float) -> dict[str, float]:
    labels = group["deterioration_label"].astype(int)
    if labels.sum() == 0:
        raise ValueError("Threshold selection requires positive deterioration events")
    for threshold in sorted(group["probability"].unique(), reverse=True):
        alerts = group["probability"] >= threshold
        recall = float((alerts & labels.eq(1)).sum() / labels.sum())
        if recall >= target:
            true_positive = int((alerts & labels.eq(1)).sum())
            return {
                "threshold": float(threshold),
                "recall": recall,
                "alert_rate": float(alerts.mean()),
                "precision": float(true_positive / alerts.sum()),
            }
    raise ValueError("No threshold meets the recall target")


def model_metrics(predictions: pd.DataFrame, target_recall: float) -> pd.DataFrame:
    """Calculate ranking and operational development metrics by model."""

    rows: list[dict[str, Any]] = []
    for model, group in predictions.groupby("model", sort=True):
        labels = group["deterioration_label"].astype(int)
        thresholds = {
            sector: _threshold_at_recall(sector_rows, target_recall)
            for sector, sector_rows in group.groupby("sector")
        }
        row_thresholds = group["sector"].map(
            {sector: values["threshold"] for sector, values in thresholds.items()}
        )
        alerts = group["probability"] >= row_thresholds
        sector_rocs = {
            sector: float(
                roc_auc_score(sector_rows["deterioration_label"], sector_rows["probability"])
            )
            for sector, sector_rows in group.groupby("sector")
            if sector_rows["deterioration_label"].nunique() == 2
        }
        rows.append(
            {
                "model": model,
                "observations": len(group),
                "event_prevalence": float(labels.mean()),
                "ROC_AUC": float(roc_auc_score(labels, group["probability"])),
                "PR_AUC": float(average_precision_score(labels, group["probability"])),
                "Brier_score": float(brier_score_loss(labels, group["probability"])),
                "alert_rate": float(alerts.mean()),
                "precision": float(precision_score(labels, alerts, zero_division=0)),
                "recall": float(recall_score(labels, alerts)),
                "F1": float(f1_score(labels, alerts)),
                "accuracy": float(accuracy_score(labels, alerts)),
                "balanced_accuracy": float(balanced_accuracy_score(labels, alerts)),
                "minimum_sector_recall": min(value["recall"] for value in thresholds.values()),
                "minimum_sector_ROC_AUC": min(sector_rocs.values()),
                "consumer_threshold": thresholds["Consumer Discretionary"]["threshold"],
                "utility_threshold": thresholds["Utilities"]["threshold"],
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["ROC_AUC", "PR_AUC", "alert_rate"], ascending=[False, False, True]
    )


def choose_champion(metrics: pd.DataFrame, config: dict[str, Any]) -> pd.Series:
    """Choose the strongest ROC model that satisfies the registered PR guardrail."""

    benchmark = float(config["metrics"]["phase2_pr_auc_benchmark"])
    eligible = metrics.loc[metrics["PR_AUC"] > benchmark].copy()
    if eligible.empty:
        eligible = metrics.copy()
    return eligible.sort_values(
        ["ROC_AUC", "PR_AUC", "alert_rate", "model"],
        ascending=[False, False, True, True],
    ).iloc[0]


def run_stage_29() -> dict[str, Any]:
    """Run and persist the complete Phase 3 development comparison."""

    root = repository_root()
    config_path = root / "configs" / "phase3.yml"
    config = read_yaml(config_path)
    processed = root / "data" / "processed"
    reports = root / "reports" / "generated"
    reports.mkdir(parents=True, exist_ok=True)
    features = pd.read_parquet(processed / "phase2_model_features.parquet")
    predictions, selections, weights = run_phase3_development(
        features, _candidate_features(root, config), config
    )
    unique = latest_prediction_per_decision(predictions)
    comparison_start = pd.Timestamp("2022-07-01")
    comparable = unique.loc[unique["decision_at"] >= comparison_start].copy()
    metrics = model_metrics(comparable, float(config["metrics"]["minimum_sector_recall"]))
    champion = choose_champion(metrics, config)
    predictions.to_parquet(processed / "phase3_rolling_oof_predictions.parquet", index=False)
    unique.to_parquet(processed / "phase3_unique_oof_predictions.parquet", index=False)
    selections.to_parquet(processed / "phase3_model_selections.parquet", index=False)
    weights.to_parquet(processed / "phase3_ensemble_weights.parquet", index=False)
    metrics.to_csv(reports / "phase3_model_comparison.csv", index=False)
    config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    record = {
        "version": config["version"],
        "evidence_level": "development_out_of_fold",
        "comparison_start": comparison_start.date().isoformat(),
        "development_end": str(config["validation"]["development_end"]),
        "sealed_test_start": str(config["validation"]["sealed_test_start"]),
        "sealed_test_end": str(config["validation"]["sealed_test_end"]),
        "champion_model": str(champion["model"]),
        "development_ROC_AUC": float(champion["ROC_AUC"]),
        "development_PR_AUC": float(champion["PR_AUC"]),
        "development_alert_rate": float(champion["alert_rate"]),
        "development_precision": float(champion["precision"]),
        "development_recall": float(champion["recall"]),
        "consumer_threshold": float(champion["consumer_threshold"]),
        "utility_threshold": float(champion["utility_threshold"]),
        "config_sha256": config_hash,
        "sealed_test_opened": False,
    }
    record_path = reports / "phase3_champion_record.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "status": "ok",
        "rolling_predictions": len(predictions),
        "unique_predictions": len(unique),
        "models": int(metrics["model"].nunique()),
        "champion": record,
        "target_ROC_AUC": float(config["metrics"]["sealed_test_target"]),
        "development_target_achieved": bool(
            champion["ROC_AUC"] >= float(config["metrics"]["sealed_test_target"])
        ),
    }
