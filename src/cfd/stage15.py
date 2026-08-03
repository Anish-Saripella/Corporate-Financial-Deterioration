"""Stage 15 champion selection, one-time holdout evaluation, and model card evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import duckdb
import joblib  # type: ignore[import-untyped]
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score  # type: ignore[import-untyped]

from cfd.config import read_yaml, repository_root
from cfd.modeling.classification import (
    available_feature_sets,
    classification_metrics,
    fit_classifier_bundle,
)


def _candidate_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (model, increment), group in predictions.groupby(["model", "feature_increment"]):
        y_true = group["deterioration_label"].astype(int).to_numpy()
        probabilities = group["probability"].to_numpy(dtype=float)
        threshold = float(group["threshold"].median())
        fold_scores = pd.Series(
            [
                average_precision_score(
                    frame["deterioration_label"].astype(int), frame["probability"]
                )
                for _, frame in group.groupby("fold_id")
            ]
        )
        sector_scores = pd.Series(
            [
                average_precision_score(
                    frame["deterioration_label"].astype(int), frame["probability"]
                )
                for _, frame in group.groupby("sector")
            ]
        )
        rows.append(
            {
                "model": model,
                "feature_increment": increment,
                "observations": len(group),
                **classification_metrics(y_true, probabilities, threshold),
                "fold_pr_auc_std": float(fold_scores.std(ddof=0)),
                "sector_pr_auc_std": float(sector_scores.std(ddof=0)),
            }
        )
    result = pd.DataFrame(rows).sort_values(
        ["PR_AUC", "Brier_score", "sector_pr_auc_std", "fold_pr_auc_std", "model"],
        ascending=[False, True, True, True, True],
    )
    result["rank"] = np.arange(1, len(result) + 1)
    result["selected"] = result["rank"].eq(1)
    return result


def _feature_importance(bundle: Any) -> pd.DataFrame:
    preprocessor = bundle.estimator.named_steps["preprocess"]
    names = preprocessor.get_feature_names_out()
    model = bundle.estimator.named_steps["model"]
    if bundle.model_name == "logistic_regression":
        values = np.asarray(model.coef_[0], dtype=float)
        kind = "coefficient"
    else:
        values = np.asarray(model.feature_importances_, dtype=float)
        kind = "gain_importance"
    return pd.DataFrame(
        {"feature": names, "importance": values, "absolute_importance": abs(values), "type": kind}
    ).sort_values("absolute_importance", ascending=False)


def run_stage_15() -> dict[str, Any]:
    root = repository_root()
    processed = root / "data" / "processed"
    reports = root / "reports" / "generated"
    artifacts = root / "artifacts"
    predictions = pd.read_parquet(processed / "classifier_oof_predictions.parquet")
    features = pd.read_parquet(processed / "model_features_with_forecasts.parquet")
    registry = read_yaml(root / "configs" / "feature_registry.yml")
    full_config = read_yaml(root / "configs" / "modeling.yml")
    config = full_config["classification"]
    selection = _candidate_metrics(predictions)
    champion = selection.loc[selection["selected"]].iloc[0]
    frozen_payload = {
        "model": champion["model"],
        "feature_increment": champion["feature_increment"],
        "selection_metric": "PR_AUC",
        "selection_value": float(champion["PR_AUC"]),
        "selected_before_holdout_evaluation": True,
    }
    frozen_payload["selection_sha256"] = hashlib.sha256(
        json.dumps(frozen_payload, sort_keys=True).encode()
    ).hexdigest()
    (reports / "champion_selection_frozen.json").write_text(
        json.dumps(frozen_payload, indent=2) + "\n", encoding="utf-8"
    )

    holdout_start = pd.Timestamp(
        read_yaml(root / "configs" / "label.yml")["label"]["audit_result"]["final_holdout_start"]
    )
    development = features.loc[
        (features["decision_at"] < holdout_start)
        & features["deterioration_label"].notna()
        & features["label_available_at"].notna()
        & (features["label_available_at"] < holdout_start)
    ].copy()
    holdout = features.loc[
        (features["decision_at"] >= holdout_start) & features["deterioration_label"].notna()
    ].copy()
    feature_sets = available_feature_sets(registry, config)
    numeric, categorical = feature_sets[str(champion["feature_increment"])]
    bundle = fit_classifier_bundle(
        development,
        model_name=str(champion["model"]),
        feature_increment=str(champion["feature_increment"]),
        numeric_features=numeric,
        categorical_features=categorical,
        config=config,
    )
    probabilities = bundle.predict_probability(holdout[[*numeric, *categorical]])
    holdout_predictions = holdout[
        ["decision_key", "cik", "decision_at", "sector", "deterioration_label"]
    ].copy()
    holdout_predictions["model"] = bundle.model_name
    holdout_predictions["feature_increment"] = bundle.feature_increment
    holdout_predictions["probability"] = probabilities
    holdout_predictions["threshold"] = bundle.threshold
    holdout_predictions["alert"] = probabilities >= bundle.threshold
    metric_rows = [
        {
            "sector": "Overall",
            "observations": len(holdout_predictions),
            **classification_metrics(
                holdout_predictions["deterioration_label"].astype(int).to_numpy(),
                probabilities,
                bundle.threshold,
            ),
        }
    ]
    for sector, group in holdout_predictions.groupby("sector"):
        metric_rows.append(
            {
                "sector": sector,
                "observations": len(group),
                **classification_metrics(
                    group["deterioration_label"].astype(int).to_numpy(),
                    group["probability"].to_numpy(dtype=float),
                    bundle.threshold,
                ),
            }
        )
    holdout_metrics = pd.DataFrame(metric_rows)
    importance = _feature_importance(bundle)
    artifacts.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, artifacts / "champion_classifier.joblib")
    selection.to_csv(reports / "classifier_model_selection.csv", index=False)
    holdout_metrics.to_csv(reports / "final_holdout_metrics.csv", index=False)
    importance.to_csv(reports / "champion_feature_importance.csv", index=False)
    holdout_predictions.to_parquet(processed / "final_holdout_predictions.parquet", index=False)
    with duckdb.connect(str(processed / "cfd.duckdb")) as connection:
        location = str(processed / "final_holdout_predictions.parquet").replace("'", "''")
        connection.execute(
            "CREATE OR REPLACE TABLE marts.final_holdout_predictions AS "
            f"SELECT * FROM read_parquet('{location}')"
        )
    result = {
        "status": "complete",
        "selection_version": "phase1-modeling-v1",
        "champion": frozen_payload,
        "development_training_rows": len(development),
        "holdout_evaluation_rows": len(holdout_predictions),
        "holdout_metrics": holdout_metrics.to_dict("records"),
        "holdout_evaluated_after_champion_freeze": True,
        "model_artifact": "artifacts/champion_classifier.joblib",
    }
    (reports / "stage15_summary.json").write_text(
        json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return result
