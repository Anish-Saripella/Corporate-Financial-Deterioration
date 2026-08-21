"""Stage 31: summarize Phase 3 evidence without changing the frozen model."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score  # type: ignore[import-untyped]

from cfd.config import read_yaml, repository_root


def clustered_metric_intervals(
    predictions: pd.DataFrame, config: dict[str, Any]
) -> dict[str, list[float]]:
    """Bootstrap complete companies to retain within-company dependence."""

    policy = config["uncertainty"]
    cluster = str(policy["cluster_column"])
    clusters = predictions[cluster].unique()
    rng = np.random.default_rng(int(policy["random_seed"]))
    values: list[tuple[float, float]] = []
    for _ in range(int(policy["bootstrap_repetitions"])):
        sampled = rng.choice(clusters, size=len(clusters), replace=True)
        frames = []
        for sample_id, value in enumerate(sampled):
            frame = predictions.loc[predictions[cluster] == value].copy()
            frame["bootstrap_cluster"] = sample_id
            frames.append(frame)
        bootstrap = pd.concat(frames, ignore_index=True)
        labels = bootstrap["deterioration_label"].astype(int)
        if labels.nunique() != 2:
            continue
        values.append(
            (
                float(roc_auc_score(labels, bootstrap["probability"])),
                float(average_precision_score(labels, bootstrap["probability"])),
            )
        )
    array = np.asarray(values, dtype=float)
    alpha = 1.0 - float(policy["confidence_level"])
    return {
        "ROC_AUC": np.quantile(array[:, 0], [alpha / 2, 1 - alpha / 2]).tolist(),
        "PR_AUC": np.quantile(array[:, 1], [alpha / 2, 1 - alpha / 2]).tolist(),
    }


def run_stage_31() -> dict[str, Any]:
    """Write auditable Phase 3 uncertainty and a concise generated summary."""

    root = repository_root()
    reports = root / "reports" / "generated"
    config = read_yaml(root / "configs" / "phase3_reporting.yml")
    metrics = json.loads((reports / "phase3_sealed_test_metrics.json").read_text(encoding="utf-8"))
    development = json.loads((reports / "phase3_champion_record.json").read_text(encoding="utf-8"))
    predictions = pd.read_parquet(
        root / "data" / "processed" / "phase3_sealed_test_predictions.parquet"
    )
    intervals = clustered_metric_intervals(predictions, config)
    evidence = {
        "development": development,
        "sealed_test": metrics,
        "company_clustered_95_percent_intervals": intervals,
    }
    (reports / "phase3_evidence_summary.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary_lines = [
        "# Phase 3 generated evidence summary",
        "",
        f"- Frozen model: `{metrics['model']}`",
        f"- Development ROC-AUC: {development['development_ROC_AUC']:.3f}",
        f"- Development PR-AUC: {development['development_PR_AUC']:.3f}",
        (
            f"- Sealed late-2024 ROC-AUC: {metrics['ROC_AUC']:.3f} "
            f"(company-clustered 95% interval {intervals['ROC_AUC'][0]:.3f}-"
            f"{intervals['ROC_AUC'][1]:.3f})"
        ),
        (
            f"- Sealed late-2024 PR-AUC: {metrics['PR_AUC']:.3f} "
            f"(company-clustered 95% interval {intervals['PR_AUC'][0]:.3f}-"
            f"{intervals['PR_AUC'][1]:.3f})"
        ),
        (
            f"- Recall: {metrics['recall']:.1%}; precision: {metrics['precision']:.1%}; "
            f"alert rate: {metrics['alert_rate']:.1%}"
        ),
        "",
        (
            f"The sealed cohort contains {metrics['observations']} observations, "
            f"{metrics['companies']} companies, and {metrics['events']} deterioration events. "
            "The intervals are wide, so the result is promising test evidence rather than "
            "proof of universal 0.80+ ROC-AUC performance."
        ),
        "",
    ]
    summary = "\n".join(summary_lines)
    (reports / "phase3_evidence_summary.md").write_text(summary, encoding="utf-8")
    return {"status": "ok", **evidence}
