"""Executable, audited workflow for Phase 1 Stages 8 through 12."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from cfd.analysis.eda import run_eda
from cfd.config import read_yaml, repository_root
from cfd.evaluation.temporal import build_expanding_window_splits
from cfd.features.engineering import engineer_historical_features
from cfd.panel import KPI_COLUMNS
from cfd.stage9 import build_and_audit_label


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )


def validate_stage_8() -> tuple[pd.DataFrame, dict[str, Any]]:
    root = repository_root()
    panel = pd.read_parquet(root / "data" / "processed" / "point_in_time_panel.parquet")
    certification = pd.read_parquet(
        root / "data" / "processed" / "company_modeling_certification.parquet"
    )
    selected = pd.read_parquet(root / "data" / "processed" / "selected_universe.parquet")
    replacements = pd.read_parquet(root / "data" / "processed" / "universe_replacements.parquet")
    failed = certification.loc[~certification["passed"]]
    if not failed.empty:
        raise ValueError(
            f"Stage 8 certification contains failed rules: {failed.head().to_dict('records')}"
        )
    if panel["cik"].nunique() != 60 or len(selected) != 60:
        raise ValueError("Stage 8 final universe is not exactly 60 companies")
    sector_counts = selected.groupby("sector").size().to_dict()
    if set(sector_counts.values()) != {30}:
        raise ValueError(f"Stage 8 sector balance failed: {sector_counts}")
    if panel["decision_key"].duplicated().any():
        raise ValueError("Stage 8 panel contains duplicate decision keys")
    if (panel["maximum_source_available_at"] > panel["decision_at"]).any():
        raise ValueError("Stage 8 financial leakage detected")
    known_macro = panel["macro_available_at_max"].notna()
    if (
        panel.loc[known_macro, "macro_available_at_max"] > panel.loc[known_macro, "decision_at"]
    ).any():
        raise ValueError("Stage 8 macro-vintage leakage detected")
    return panel, {
        "status": "complete",
        "universe_version": "selected-universe-v2-certified",
        "companies": int(panel["cik"].nunique()),
        "panel_rows": len(panel),
        "sector_counts": sector_counts,
        "certification_rules": len(certification),
        "failed_certification_rules": 0,
        "replacements": len(replacements),
        "duplicate_decision_keys": 0,
        "financial_leakage_rows": 0,
        "macro_leakage_rows": 0,
    }


def complete_stage_11(labeled: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    root = repository_root()
    registry = read_yaml(root / "configs" / "feature_registry.yml")
    engineered = engineer_historical_features(labeled)
    required = set(registry["numeric_features"] + registry["categorical_features"])
    missing = required - set(engineered.columns)
    if missing:
        raise ValueError(f"Feature registry columns are missing: {sorted(missing)}")
    identity_and_outcome = [
        "decision_key",
        "cik",
        "decision_at",
        "period_end",
        "label_available_at",
        "deterioration_label",
        "deterioration_episode_start",
        "feature_available_at",
    ]
    registered = registry["numeric_features"] + registry["categorical_features"]
    indicators = [
        f"{column}_missing"
        for column in registry["numeric_features"]
        if f"{column}_missing" in engineered
    ]
    model_columns = list(dict.fromkeys([*identity_and_outcome, *registered, *indicators]))
    features = engineered[model_columns].copy()
    features.to_parquet(root / "data" / "processed" / "model_features.parquet", index=False)
    dictionary_rows: list[dict[str, Any]] = []
    for column in registry["numeric_features"]:
        dictionary_rows.append(
            {
                "feature": column,
                "type": "numeric",
                "availability": "decision_time_or_earlier",
                "fold_fitted_processing": "median_imputation, 1%-99% clipping, optional scaling",
            }
        )
    for column in registry["categorical_features"]:
        dictionary_rows.append(
            {
                "feature": column,
                "type": "categorical",
                "availability": "frozen_universe_metadata",
                "fold_fitted_processing": (
                    "most-frequent imputation and unknown-safe one-hot encoding"
                ),
            }
        )
    pd.DataFrame(dictionary_rows).to_csv(
        root / "reports" / "generated" / "feature_dictionary.csv", index=False
    )
    future_feature_names = [
        column for column in features.columns if column.startswith("future_") and column in required
    ]
    if future_feature_names:
        raise ValueError(f"Future outcome columns entered feature registry: {future_feature_names}")
    return features, {
        "status": "complete",
        "feature_registry_version": registry["version"],
        "rows": len(features),
        "registered_numeric_features": len(registry["numeric_features"]),
        "registered_categorical_features": len(registry["categorical_features"]),
        "duplicate_decision_keys": int(features["decision_key"].duplicated().sum()),
        "future_outcome_features": future_feature_names,
        "fold_local_preprocessing_required": True,
    }


def complete_stage_12(features: pd.DataFrame) -> dict[str, Any]:
    root = repository_root()
    config = read_yaml(root / "configs" / "temporal_validation.yml")
    holdout_start = str(
        read_yaml(root / "configs" / "label.yml")["label"]["audit_result"]["final_holdout_start"]
    )
    assignments, holdout, folds = build_expanding_window_splits(
        features,
        holdout_start=holdout_start,
        minimum_training_quarters=int(config["minimum_training_quarters"]),
        validation_window_quarters=int(config["validation_window_quarters"]),
        step_quarters=int(config["step_quarters"]),
    )
    processed = root / "data" / "processed"
    reports = root / "reports" / "generated"
    assignments.to_parquet(processed / "temporal_split_assignments.parquet", index=False)
    holdout.to_parquet(processed / "final_holdout_locked.parquet", index=False)
    pd.DataFrame(folds).to_csv(reports / "temporal_fold_summary.csv", index=False)
    _write_json(reports / "evaluation_policy.json", config)
    holdout_events = holdout.groupby("sector").agg(
        labeled_rows=("deterioration_label", "count"),
        positive_rows=("deterioration_label", lambda values: int((values == 1).sum())),
        distinct_episodes=("deterioration_episode_start", "sum"),
    )
    return {
        "status": "complete",
        "validation_version": config["version"],
        "folds": len(folds),
        "fold_boundaries": folds,
        "final_holdout_start": holdout_start,
        "final_holdout_rows": len(holdout),
        "final_holdout_event_counts": holdout_events.to_dict("index"),
        "label_horizon_embargo_quarters": int(config["embargo_quarters"]),
        "model_development_access_to_final_holdout": False,
        "primary_classification_metric": config["classification_metric_hierarchy"]["primary"],
    }


def _persist_marts() -> None:
    root = repository_root()
    processed = root / "data" / "processed"
    tables = {
        "point_in_time_panel": "point_in_time_panel.parquet",
        "company_modeling_certification": "company_modeling_certification.parquet",
        "universe_replacements": "universe_replacements.parquet",
        "labeled_company_quarters": "labeled_company_quarters.parquet",
        "model_features": "model_features.parquet",
        "temporal_split_assignments": "temporal_split_assignments.parquet",
        "final_holdout_locked": "final_holdout_locked.parquet",
    }
    with duckdb.connect(str(processed / "cfd.duckdb")) as connection:
        for table, filename in tables.items():
            location = str(processed / filename).replace("'", "''")
            connection.execute(
                f"CREATE OR REPLACE TABLE marts.{table} AS SELECT * FROM read_parquet('{location}')"
            )


def run_stages_8_to_12() -> dict[str, Any]:
    panel, stage_8 = validate_stage_8()
    labeled, stage_9 = build_and_audit_label(panel)
    stage_10 = run_eda(labeled)
    features, stage_11 = complete_stage_11(labeled)
    stage_12 = complete_stage_12(features)
    _persist_marts()
    summary = {
        "stage_8": stage_8,
        "stage_9": stage_9,
        "stage_10": stage_10,
        "stage_11": stage_11,
        "stage_12": stage_12,
        "kpis": KPI_COLUMNS,
    }
    _write_json(repository_root() / "reports" / "generated" / "stages_8_12_summary.json", summary)
    return summary
