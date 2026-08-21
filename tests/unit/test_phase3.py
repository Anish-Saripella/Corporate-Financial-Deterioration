from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from cfd.modeling.phase3 import (
    add_prior_deterioration_features,
    shrunk_performance_weights,
)
from cfd.stage29 import choose_champion, latest_prediction_per_decision
from cfd.stage30 import run_stage_30


def test_prior_deterioration_features_use_only_available_labels() -> None:
    training = pd.DataFrame(
        {
            "cik": [1, 1],
            "decision_at": pd.to_datetime(["2020-01-01", "2021-01-01"]),
            "label_available_at": pd.to_datetime(["2021-01-01", "2023-01-01"]),
            "deterioration_label": [1, 1],
        }
    )
    scoring = pd.DataFrame(
        {
            "cik": [1],
            "decision_at": pd.to_datetime(["2022-01-01"]),
        }
    )

    _, transformed = add_prior_deterioration_features(training, scoring, pd.Timestamp("2022-01-01"))

    assert transformed.loc[0, "prior_deterioration_rate"] == pytest.approx(2 / 6)
    assert transformed.loc[0, "prior_deterioration_evidence"] == pytest.approx(0.693147)


def test_performance_weights_are_shrunk_and_normalized() -> None:
    weights = shrunk_performance_weights({"strong": 0.80, "weak": 0.60}, shrinkage=0.50)

    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights["strong"] > weights["weak"]
    assert weights["weak"] > 0.25


def test_latest_prediction_uses_closest_prior_origin() -> None:
    predictions = pd.DataFrame(
        {
            "decision_key": ["a", "a"],
            "model": ["m", "m"],
            "origin": pd.to_datetime(["2022-01-01", "2022-04-01"]),
            "probability": [0.20, 0.30],
        }
    )

    latest = latest_prediction_per_decision(predictions)

    assert len(latest) == 1
    assert latest.loc[0, "probability"] == 0.30


def test_champion_requires_pr_auc_guardrail() -> None:
    metrics = pd.DataFrame(
        {
            "model": ["high_roc_low_pr", "eligible"],
            "ROC_AUC": [0.90, 0.82],
            "PR_AUC": [0.30, 0.45],
            "alert_rate": [0.40, 0.45],
        }
    )
    config = {"metrics": {"phase2_pr_auc_benchmark": 0.412}}

    champion = choose_champion(metrics, config)

    assert champion["model"] == "eligible"


def test_final_test_cannot_be_opened_twice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path
    (root / "configs").mkdir()
    (root / "reports" / "generated").mkdir(parents=True)
    (root / "configs" / "phase3.yml").write_text("version: test\n", encoding="utf-8")
    (root / "reports" / "generated" / "phase3_champion_record.json").write_text(
        json.dumps({"sealed_test_opened": True}), encoding="utf-8"
    )
    monkeypatch.setattr("cfd.stage30.repository_root", lambda: root)

    with pytest.raises(RuntimeError, match="already been evaluated"):
        run_stage_30()
