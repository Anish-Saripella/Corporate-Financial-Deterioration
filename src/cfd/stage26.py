"""Stage 26: materialize Phase 2 interpretation, monitoring, and governance."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sklearn.metrics import (  # type: ignore[import-untyped]
    average_precision_score,
    brier_score_loss,
)

from cfd.analysis.interpretability import build_company_explanations
from cfd.config import read_yaml, repository_root
from cfd.phase2.monitoring import feature_monitoring_report


def _choose_development_specification(predictions: pd.DataFrame) -> tuple[str, str]:
    """Use the registered partially pooled primary architecture."""

    rows: list[dict[str, Any]] = []
    for (model, increment), group in predictions.groupby(["model", "feature_increment"]):
        rows.append(
            {
                "model": model,
                "feature_increment": increment,
                "pr_auc": average_precision_score(
                    group["deterioration_label"], group["probability"]
                ),
            }
        )
    ranked = pd.DataFrame(rows)
    primary = ranked.loc[ranked["model"] == "partially_pooled_logistic"]
    if primary.empty:
        raise ValueError("Registered partially pooled primary model is absent")
    winner = primary.sort_values(
        ["pr_auc", "model", "feature_increment"], ascending=[False, True, True]
    ).iloc[0]
    return str(winner["model"]), str(winner["feature_increment"])


def build_recall_first_policy_table(
    predictions: pd.DataFrame, recall_targets: list[float]
) -> pd.DataFrame:
    """Choose the least-work sector threshold meeting each registered recall target."""

    rows: list[dict[str, Any]] = []
    sectors = sorted(predictions["sector"].unique())
    for target in recall_targets:
        thresholds: dict[str, float] = {}
        sector_recalls: dict[str, float] = {}
        for sector in sectors:
            group = predictions.loc[predictions["sector"] == sector]
            labels = group["deterioration_label"].astype(int)
            if labels.sum() == 0:
                raise ValueError(f"Recall policy cannot be estimated without {sector} events")
            candidates: list[dict[str, float]] = []
            for threshold in sorted(group["probability"].unique(), reverse=True):
                alert = group["probability"] >= threshold
                true_positive = int((alert & labels.eq(1)).sum())
                recall = true_positive / int(labels.sum())
                if recall >= target:
                    candidates.append(
                        {
                            "threshold": float(threshold),
                            "recall": recall,
                            "alert_rate": float(alert.mean()),
                        }
                    )
            chosen = sorted(
                candidates, key=lambda item: (item["alert_rate"], -item["threshold"])
            )[0]
            thresholds[sector] = chosen["threshold"]
            sector_recalls[sector] = chosen["recall"]
        row_thresholds = predictions["sector"].map(thresholds)
        alerts = predictions["probability"] >= row_thresholds
        labels = predictions["deterioration_label"].astype(int)
        true_positive = int((alerts & labels.eq(1)).sum())
        rows.append(
            {
                "required_recall": target,
                "alert_rate": float(alerts.mean()),
                "precision": true_positive / int(alerts.sum()),
                "overall_recall": true_positive / int(labels.sum()),
                "consumer_recall": sector_recalls["Consumer Discretionary"],
                "utility_recall": sector_recalls["Utilities"],
                "consumer_threshold": thresholds["Consumer Discretionary"],
                "utility_threshold": thresholds["Utilities"],
                "sector_specific_thresholds": True,
                "minimum_workload_subject_to_recall": True,
            }
        )
    return pd.DataFrame(rows)


def run_stage_26() -> dict[str, Any]:
    """Create auditable development explanations and drift evidence from real rows."""

    root = repository_root()
    processed = root / "data" / "processed"
    reports = root / "reports" / "generated"
    config = read_yaml(root / "configs" / "phase2.yml")
    features = pd.read_parquet(processed / "phase2_model_features.parquet")
    predictions = pd.read_parquet(processed / "phase2_oof_predictions.parquet")
    model, increment = _choose_development_specification(predictions)
    selected = predictions.loc[
        (predictions["model"] == model)
        & (predictions["feature_increment"] == increment)
    ].copy()
    explanation_input = selected.merge(
        features,
        on="decision_key",
        how="left",
        validate="one_to_one",
        suffixes=("", "_feature"),
    )
    reference = features.loc[features["decision_at"] < pd.Timestamp("2023-01-01")]
    explanations = build_company_explanations(
        explanation_input,
        reference,
        maximum_reasons=int(config["interpretability"]["maximum_reason_codes"]),
    )
    explanations["model"] = model
    explanations["feature_increment"] = increment
    explanations.to_csv(reports / "phase2_company_explanations.csv", index=False)

    monitor_features = [
        column
        for column in [
            "interest_coverage_ttm",
            "free_cash_flow_margin_ttm",
            "total_debt_to_assets",
            "current_ratio",
            "operating_margin_ttm",
            "filing_delay_days",
            "source_quality_score",
        ]
        if column in features
    ]
    current = features.loc[features["decision_at"] >= pd.Timestamp("2023-01-01")]
    monitoring = feature_monitoring_report(reference, current, monitor_features, config)
    monitoring["reference_period"] = "before_2023"
    monitoring["current_period"] = "2023_through_2025_cutoff"
    monitoring.to_csv(reports / "phase2_feature_monitoring.csv", index=False)

    calibrated = pd.read_parquet(processed / "phase2_calibrated_oof_predictions.parquet")
    calibration_rows: list[dict[str, Any]] = []
    for keys, group in calibrated.groupby(
        ["model", "feature_increment", "calibration_method", "calibration_scope"]
    ):
        calibration_rows.append(
            {
                "model": keys[0],
                "feature_increment": keys[1],
                "calibration_method": keys[2],
                "calibration_scope": keys[3],
                "observations": len(group),
                "PR_AUC": average_precision_score(
                    group["deterioration_label"], group["probability"]
                ),
                "Brier_score": brier_score_loss(
                    group["deterioration_label"], group["probability"]
                ),
            }
        )
    calibration_comparison = pd.DataFrame(calibration_rows)
    calibration_comparison.to_csv(
        reports / "phase2_calibration_method_comparison.csv", index=False
    )
    champion_calibration = calibration_comparison.loc[
        (calibration_comparison["model"] == model)
        & (calibration_comparison["feature_increment"] == increment)
    ].sort_values(["Brier_score", "calibration_method"]).iloc[0]
    calibrated_champion_rows = calibrated.loc[
        (calibrated["model"] == model)
        & (calibrated["feature_increment"] == increment)
        & (calibrated["calibration_method"] == champion_calibration["calibration_method"])
        & (calibrated["calibration_scope"] == champion_calibration["calibration_scope"])
    ].copy()
    policy = config["decision_policy"]
    policy_table = build_recall_first_policy_table(
        selected, [float(value) for value in policy["recall_sensitivity_targets"]]
    )
    policy_table.to_csv(reports / "phase2_recall_first_threshold_table.csv", index=False)
    target_recall = float(policy["target_recall_within_each_sector"])
    selected_policy = policy_table.loc[
        policy_table["required_recall"].sub(target_recall).abs() < 1e-9
    ].iloc[0]
    pd.DataFrame(
        [
            {
                "model": model,
                "feature_increment": increment,
                "calibration_method": champion_calibration["calibration_method"],
                "calibration_scope": champion_calibration["calibration_scope"],
                **selected_policy.to_dict(),
                "selected_on_development_only": True,
            }
        ]
    ).to_csv(reports / "phase2_development_policy_selection.csv", index=False)
    sector_thresholds = {
        "Consumer Discretionary": float(selected_policy["consumer_threshold"]),
        "Utilities": float(selected_policy["utility_threshold"]),
    }
    explanations = explanations.merge(
        selected[["cik", "decision_at", "sector"]],
        on=["cik", "decision_at"],
        how="left",
        validate="one_to_one",
    )
    explanations["development_alert"] = explanations.apply(
        lambda row: row["probability"] >= sector_thresholds[str(row["sector"])], axis=1
    )
    explanations["target_sector_recall"] = target_recall
    explanations.to_csv(reports / "phase2_company_explanations.csv", index=False)

    labels = selected["deterioration_label"].astype(int)
    probabilities = selected["probability"].astype(float)
    calibration_error = float(
        abs(
            calibrated_champion_rows["probability"].mean()
            - calibrated_champion_rows["deterioration_label"].mean()
        )
    )
    alert_rate = float(selected_policy["alert_rate"])
    source_cutoff = pd.Timestamp(config["universe_policy"]["financial_history_cutoff"])
    latest_decision = pd.to_datetime(features["decision_at"]).max()
    reference_mix = reference["sector"].value_counts(normalize=True)
    current_mix = current["sector"].value_counts(normalize=True)
    largest_mix_change = float(
        max(
            abs(current_mix.get(sector, 0.0) - reference_mix.get(sector, 0.0))
            for sector in set(reference_mix.index) | set(current_mix.index)
        )
    )
    operational = pd.DataFrame(
        [
            {
                "monitor": "source_freshness",
                "value": float((source_cutoff - latest_decision.normalize()).days),
                "unit": "days_before_financial_cutoff",
                "status": "normal" if latest_decision <= source_cutoff else "failure",
                "action": "continue_monitoring"
                if latest_decision <= source_cutoff
                else config["monitoring"]["actions"]["source_freshness_failure"],
            },
            {
                "monitor": "largest_sector_mix_change",
                "value": largest_mix_change,
                "unit": "absolute_share_change",
                "status": "warning" if largest_mix_change >= 0.05 else "normal",
                "action": "investigate_population_composition"
                if largest_mix_change >= 0.05
                else "continue_monitoring",
            },
            {
                "monitor": "matured_event_rate",
                "value": float(labels.mean()),
                "unit": "share",
                "status": "diagnostic",
                "action": "compare_with_training_event_rate",
            },
            {
                "monitor": "ranking_PR_AUC",
                "value": float(average_precision_score(labels, probabilities)),
                "unit": "score",
                "status": "development_only",
                "action": "reconsider_features_and_model_on_confirmed_failure",
            },
            {
                "monitor": "calibration_error",
                "value": calibration_error,
                "unit": "absolute_mean_probability_error",
                "status": "warning"
                if calibration_error
                >= float(config["monitoring"]["calibration_error_warning"])
                else "normal",
                "action": config["monitoring"]["actions"]["calibration_failure"]
                if calibration_error
                >= float(config["monitoring"]["calibration_error_warning"])
                else "continue_monitoring",
            },
            {
                "monitor": "alert_rate",
                "value": alert_rate,
                "unit": "share",
                "status": "warning"
                if alert_rate > float(config["monitoring"]["alert_rate_upper"])
                else "normal",
                "action": "review_threshold_and_analyst_capacity"
                if alert_rate > float(config["monitoring"]["alert_rate_upper"])
                else "continue_monitoring",
            },
        ]
    )
    operational.to_csv(reports / "phase2_operational_monitoring.csv", index=False)
    case_rows = selected[
        ["decision_key", "cik", "decision_at", "sector", "deterioration_label", "probability"]
    ].copy()
    case_rows["alert"] = case_rows.apply(
        lambda row: row["probability"] >= sector_thresholds[str(row["sector"])], axis=1
    )
    case_rows["case_type"] = "true_negative"
    case_rows.loc[case_rows["alert"] & case_rows["deterioration_label"].eq(1), "case_type"] = (
        "true_positive"
    )
    case_rows.loc[case_rows["alert"] & case_rows["deterioration_label"].eq(0), "case_type"] = (
        "false_positive"
    )
    case_rows.loc[~case_rows["alert"] & case_rows["deterioration_label"].eq(1), "case_type"] = (
        "false_negative"
    )
    disagreement = predictions.groupby("decision_key")["probability"].std().rename(
        "model_probability_std"
    )
    case_rows = case_rows.merge(disagreement, on="decision_key", how="left")
    explanation_fields = explanations[
        ["cik", "decision_at", "reason_codes_json", "interpretation_limit"]
    ]
    case_rows = case_rows.merge(
        explanation_fields, on=["cik", "decision_at"], how="left", validate="one_to_one"
    )
    priority_parts = [
        group.nlargest(5, "probability" if name != "false_negative" else "model_probability_std")
        for name, group in case_rows.loc[
            case_rows["case_type"].isin(["true_positive", "false_positive", "false_negative"])
        ].groupby("case_type")
    ]
    priority_parts.append(
        case_rows.nlargest(5, "model_probability_std").assign(case_type="unstable")
    )
    review_queue = pd.concat(priority_parts, ignore_index=True).drop_duplicates("decision_key")
    review_queue["human_review_completed"] = False
    review_queue["review_prompt"] = (
        "Check SEC filing context, one-time items, regulation/capital cycle, and whether the "
        "reason codes omit material financial information."
    )
    review_queue.to_csv(reports / "phase2_analyst_case_review_queue.csv", index=False)

    readiness = json.loads((reports / "phase2_readiness.json").read_text(encoding="utf-8"))
    universe = pd.read_parquet(processed / "phase2_selected_universe.parquet")
    universe_sector_counts = universe.groupby("sector")["cik"].nunique().to_dict()
    strict_count = int(universe["strict_phase1_certified"].sum())
    flagged_count = int((~universe["strict_phase1_certified"]).sum())
    card = f"""# Phase 2 Development Model and Data Card

## Intended use

Rank currently active Consumer Discretionary and Utility issuers for analyst review of possible
four-quarter deterioration in debt-service capacity. This is not a default probability, credit
rating, causal conclusion, or trading recommendation.

## Data and population

- {universe_sector_counts['Consumer Discretionary']} Consumer Discretionary and
  {universe_sector_counts['Utilities']} Utility issuers at the August 2, 2026 selection date.
- Financial history is capped at December 31, 2025 and comes from SEC EDGAR and FRED/ALFRED.
- Delisted firms are excluded, so survivorship bias limits generalization.
- Former strict Phase 1 certification: {strict_count} issuers; {flagged_count} retained with visible
  quality flags and company-quarter modeling eligibility.
- Sampling uses seed 20260802, industry/size strata, no replacement, and frozen same-sector
  reserves.

## Development model

The leading development specification is `{model}` with `{increment}`. Selection uses temporal
out-of-fold PR-AUC only. It does not use a new final test period. The partially pooled logistic
model is the interpretable primary model, pooled logistic is the benchmark, and constrained
gradient boosting is the nonlinear challenger.

## Interpretation

Company reason codes identify unusually weak ratios, adverse changes, peer position, macro stress,
forecast uncertainty, or source-quality conditions. They describe associations, not causes.

## Monitoring and actions

PSI of 0.10 is a warning and 0.25 is an escalation. Missingness increases of 0.05 are warnings.
Drift triggers investigation, not automatic retraining. Calibration failure calls for recalibration
on matured outcomes; ranking failure calls for model and feature review.

## Validation status

Readiness status: `{readiness['status']}`. Final test may be opened:
`{readiness['final_test_may_be_opened']}`.
The 2023+ Phase 1 benchmark is consumed and is used only for development analysis. A genuinely new
future period with matured four-quarter outcomes is required for a final Phase 2 performance claim.
"""
    (reports / "phase2_model_and_data_card.md").write_text(card, encoding="utf-8")
    result = {
        "status": "complete",
        "development_model": model,
        "feature_increment": increment,
        "explanations": len(explanations),
        "monitoring_features": len(monitoring),
        "monitoring_warnings": int((monitoring["severity"] != "normal").sum()),
        "operational_monitoring_checks": len(operational),
        "analyst_case_review_rows": len(review_queue),
        "selected_calibration_method": champion_calibration["calibration_method"],
        "target_recall_within_each_sector": target_recall,
        "consumer_threshold": sector_thresholds["Consumer Discretionary"],
        "utility_threshold": sector_thresholds["Utilities"],
        "selected_policy_alert_rate": float(selected_policy["alert_rate"]),
        "selected_policy_precision": float(selected_policy["precision"]),
        "final_test_evaluated": False,
        "synthetic_data_used": False,
    }
    (reports / "stage26_summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result
