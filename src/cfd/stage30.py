"""Stage 30: one-time evaluation of the frozen Phase 3 late-2024 test."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
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
from cfd.modeling.phase3 import (
    HISTORICAL_RISK_FEATURES,
    _training_rows,
    add_contemporaneous_warning_features,
    add_prior_deterioration_features,
    screen_features,
    select_and_fit_models,
    shrunk_performance_weights,
)
from cfd.stage29 import _candidate_features


def _base_probabilities(
    models: dict[str, Any], scoring: pd.DataFrame, columns: list[str]
) -> dict[str, np.ndarray[Any, Any]]:
    return {
        name: estimator.predict_proba(scoring[columns])[:, 1] for name, estimator in models.items()
    }


def _adaptive_weights(
    raw_oof: pd.DataFrame, base_names: list[str], config: dict[str, Any]
) -> dict[str, float]:
    completed = raw_oof.loc[raw_oof["model"].isin(base_names)].copy()
    scores: dict[str, float] = {}
    for model in base_names:
        model_rows = completed.loc[completed["model"] == model]
        fold_scores = []
        for _, group in model_rows.groupby("fold_id"):
            if group["deterioration_label"].nunique() == 2:
                fold_scores.append(
                    float(roc_auc_score(group["deterioration_label"], group["probability"]))
                )
        scores[model] = float(np.mean(fold_scores))
    return shrunk_performance_weights(
        scores, float(config["ensembles"]["adaptive_equal_weight_shrinkage"])
    )


def _champion_probability(
    champion: str,
    probabilities: dict[str, np.ndarray[Any, Any]],
    inner_scores: dict[str, float],
    scoring: pd.DataFrame,
    config: dict[str, Any],
    root: Path,
) -> np.ndarray[Any, Any]:
    if champion in probabilities:
        return probabilities[champion]
    names = sorted(probabilities)
    matrix = np.column_stack([probabilities[name] for name in names])
    if champion == "ensemble_simple_average":
        return matrix.mean(axis=1)
    if champion == "ensemble_rank_average":
        return pd.DataFrame(matrix).rank(pct=True).mean(axis=1).to_numpy()
    if champion == "ensemble_top3_average":
        top = sorted(inner_scores, key=lambda name: inner_scores[name], reverse=True)[:3]
        return np.column_stack([probabilities[name] for name in top]).mean(axis=1)
    if champion == "ensemble_inner_winner":
        return probabilities[max(inner_scores, key=lambda name: inner_scores[name])]
    if champion == "ensemble_xgb_sector_blend":
        sector_weight = float(config["ensembles"]["xgb_sector_specific_weight"])
        return (1.0 - sector_weight) * probabilities["xgboost"] + sector_weight * probabilities[
            "sector_specific_xgboost"
        ]
    if champion == "ensemble_xgb_rf_blend":
        return 0.70 * probabilities["xgboost"] + 0.30 * probabilities["random_forest"]
    if champion == "ensemble_static_weighted":
        weights = shrunk_performance_weights(
            inner_scores, float(config["ensembles"]["static_equal_weight_shrinkage"])
        )
        return np.sum(
            np.column_stack([probabilities[name] * weight for name, weight in weights.items()]),
            axis=1,
        )
    if champion == "ensemble_adaptive_weighted":
        raw = pd.read_parquet(
            root / "data" / "processed" / "phase3_rolling_oof_predictions.parquet"
        )
        weights = _adaptive_weights(raw, names, config)
        return np.sum(
            np.column_stack([probabilities[name] * weight for name, weight in weights.items()]),
            axis=1,
        )
    if champion == "ensemble_stacking":
        unique = pd.read_parquet(
            root / "data" / "processed" / "phase3_unique_oof_predictions.parquet"
        )
        base = unique.loc[unique["model"].isin(names)]
        wide = base.pivot(index="decision_key", columns="model", values="probability").dropna()
        labels = (
            base.drop_duplicates("decision_key")
            .set_index("decision_key")
            .loc[wide.index, "deterioration_label"]
            .astype(int)
        )
        meta = LogisticRegression(C=0.10, max_iter=2000, random_state=int(config["random_seed"]))
        meta.fit(wide[names], labels)
        return np.asarray(meta.predict_proba(pd.DataFrame(probabilities)[names])[:, 1], dtype=float)
    raise ValueError(f"Unknown frozen Phase 3 champion: {champion}")


def run_stage_30() -> dict[str, Any]:
    """Open and score the sealed late-2024 test exactly once."""

    root = repository_root()
    reports = root / "reports" / "generated"
    processed = root / "data" / "processed"
    config_path = root / "configs" / "phase3.yml"
    config = read_yaml(config_path)
    record_path = reports / "phase3_champion_record.json"
    if not record_path.exists():
        raise FileNotFoundError("Run and freeze Phase 3 development before final evaluation")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if record.get("sealed_test_opened"):
        raise RuntimeError("The Phase 3 sealed test has already been evaluated")
    current_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    if record["config_sha256"] != current_hash:
        raise RuntimeError("Phase 3 configuration changed after champion freeze")
    features = pd.read_parquet(processed / "phase2_model_features.parquet")
    features["decision_at"] = pd.to_datetime(features["decision_at"])
    features["label_available_at"] = pd.to_datetime(features["label_available_at"])
    features = add_contemporaneous_warning_features(features)
    origin = pd.Timestamp(config["validation"]["sealed_test_start"])
    test_end = pd.Timestamp(config["validation"]["sealed_test_end"])
    training = _training_rows(features, origin, config)
    scoring = features.loc[
        features["decision_at"].between(origin, test_end, inclusive="both")
        & features["deterioration_label"].notna()
    ].copy()
    if scoring.empty or scoring["deterioration_label"].nunique() != 2:
        raise ValueError("Sealed test does not contain a mature two-class outcome sample")
    training, scoring = add_prior_deterioration_features(training, scoring, origin)
    candidates = [*_candidate_features(root, config), *HISTORICAL_RISK_FEATURES]
    numeric = screen_features(training, candidates, config)
    categorical = [column for column in config["features"]["categorical"] if column in features]
    models, inner_scores, _selections = select_and_fit_models(
        training, numeric, categorical, config
    )
    columns = [*numeric, *categorical]
    probabilities = _base_probabilities(models, scoring, columns)
    champion = str(record["champion_model"])
    probability = _champion_probability(
        champion, probabilities, inner_scores, scoring, config, root
    )
    output = scoring[
        [
            "decision_key",
            "cik",
            "company_name",
            "ticker",
            "decision_at",
            "sector",
            "deterioration_label",
        ]
    ].copy()
    output["model"] = champion
    output["probability"] = probability
    thresholds = {
        "Consumer Discretionary": float(record["consumer_threshold"]),
        "Utilities": float(record["utility_threshold"]),
    }
    output["threshold"] = output["sector"].map(thresholds)
    output["alert"] = output["probability"] >= output["threshold"]
    labels = output["deterioration_label"].astype(int)
    metrics: dict[str, Any] = {
        "evidence_level": "sealed_late_2024_out_of_time_test",
        "model": champion,
        "observations": len(output),
        "companies": int(output["cik"].nunique()),
        "events": int(labels.sum()),
        "event_prevalence": float(labels.mean()),
        "ROC_AUC": float(roc_auc_score(labels, output["probability"])),
        "PR_AUC": float(average_precision_score(labels, output["probability"])),
        "Brier_score": float(brier_score_loss(labels, output["probability"])),
        "alert_rate": float(output["alert"].mean()),
        "precision": float(precision_score(labels, output["alert"], zero_division=0)),
        "recall": float(recall_score(labels, output["alert"])),
        "F1": float(f1_score(labels, output["alert"])),
        "accuracy": float(accuracy_score(labels, output["alert"])),
        "balanced_accuracy": float(balanced_accuracy_score(labels, output["alert"])),
        "ROC_AUC_target": float(config["metrics"]["sealed_test_target"]),
    }
    sector_rows = []
    for sector, group in output.groupby("sector"):
        sector_labels = group["deterioration_label"].astype(int)
        sector_rows.append(
            {
                "sector": sector,
                "observations": len(group),
                "events": int(sector_labels.sum()),
                "ROC_AUC": float(roc_auc_score(sector_labels, group["probability"])),
                "PR_AUC": float(average_precision_score(sector_labels, group["probability"])),
                "alert_rate": float(group["alert"].mean()),
                "precision": float(precision_score(sector_labels, group["alert"], zero_division=0)),
                "recall": float(recall_score(sector_labels, group["alert"])),
            }
        )
    output.to_parquet(processed / "phase3_sealed_test_predictions.parquet", index=False)
    pd.DataFrame(sector_rows).to_csv(reports / "phase3_sealed_test_sector_metrics.csv", index=False)
    (reports / "phase3_sealed_test_metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    record["sealed_test_opened"] = True
    record["sealed_test_metrics_file"] = "phase3_sealed_test_metrics.json"
    record["sealed_test_ROC_AUC"] = metrics["ROC_AUC"]
    record["sealed_test_PR_AUC"] = metrics["PR_AUC"]
    record["sealed_test_target_achieved"] = bool(
        metrics["ROC_AUC"] >= float(config["metrics"]["sealed_test_target"])
    )
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"status": "ok", "metrics": metrics, "sector_metrics": sector_rows}
