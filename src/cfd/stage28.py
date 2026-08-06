# ruff: noqa: E501
# mypy: disable-error-code="no-any-return,unreachable,operator,return-value,var-annotated,unused-ignore"
"""Stage 28: controlled two-quarter versus four-quarter horizon experiment."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (  # type: ignore[import-untyped]
    average_precision_score,
    brier_score_loss,
)

from cfd.analysis.interpretability import company_reason_codes
from cfd.config import read_yaml, repository_root
from cfd.evaluation.phase2 import brier_decomposition
from cfd.features.engineering import engineer_historical_features
from cfd.features.phase2 import engineer_phase2_financial_features
from cfd.labels.deterioration import deterioration_diagnostics
from cfd.modeling.calibration import cross_fitted_temporal_calibration
from cfd.modeling.feature_selection import select_features_temporally
from cfd.modeling.phase2 import run_nested_logistic_architectures
from cfd.stage23 import INTERPRETABLE_CANDIDATE_FEATURES
from cfd.stage26 import build_recall_first_policy_table


def _features_for_horizon(panel: pd.DataFrame, horizon: int) -> pd.DataFrame:
    labeled = deterioration_diagnostics(panel, horizon=horizon)
    features = engineer_historical_features(labeled)
    return engineer_phase2_financial_features(features)


def _first_breach_lead(frame: pd.DataFrame, horizon: int) -> pd.Series:
    """Return quarters from decision to the first qualifying future coverage breach."""

    output = pd.Series(pd.NA, index=frame.index, dtype="Int8")
    ordered = frame.sort_values(["cik", "period_end"])
    for _, company in ordered.groupby("cik", sort=False):
        coverage = company["interest_coverage_ttm"].astype(float)
        for position, index in enumerate(company.index):
            current = coverage.iloc[position]
            if pd.isna(current):
                continue
            future = coverage.iloc[position + 1 : position + horizon + 1]
            for lead, value in enumerate(future, start=1):
                if pd.isna(value):
                    break
                decline = (current - value) / max(abs(current), np.finfo(float).eps)
                if value < 1.5 and decline >= 0.40:
                    output.loc[index] = lead
                    break
    return output


def _expected_calibration_error(labels: pd.Series, scores: pd.Series, bins: int = 10) -> float:
    data = pd.DataFrame({"label": labels.astype(int), "score": scores.astype(float)})
    data["bin"] = pd.qcut(data["score"], q=min(bins, data["score"].nunique()), duplicates="drop")
    value = 0.0
    for _, group in data.groupby("bin", observed=True):
        value += len(group) / len(data) * abs(group["score"].mean() - group["label"].mean())
    return float(value)


def _calibrated_primary(
    raw: pd.DataFrame, methods: list[str]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    primary = raw.loc[raw["model"].eq("partially_pooled_logistic")].copy()
    candidates = []
    for sector_specific in [False, True]:
        calibrated = cross_fitted_temporal_calibration(
            primary, methods, sector_specific=sector_specific
        )
        if not calibrated.empty:
            candidates.append(calibrated)
    all_rows = pd.concat(candidates, ignore_index=True)
    comparison = []
    for keys, group in all_rows.groupby(["calibration_method", "calibration_scope"]):
        comparison.append(
            {
                "calibration_method": keys[0],
                "calibration_scope": keys[1],
                "Brier_score": brier_score_loss(group["deterioration_label"], group["probability"]),
                "rows": len(group),
            }
        )
    table = pd.DataFrame(comparison).sort_values(
        ["Brier_score", "calibration_method", "calibration_scope"]
    )
    winner = table.iloc[0].to_dict()
    selected = all_rows.loc[
        all_rows["calibration_method"].eq(winner["calibration_method"])
        & all_rows["calibration_scope"].eq(winner["calibration_scope"])
    ].copy()
    return selected, winner


def _summarize_horizon(
    horizon: int,
    predictions: pd.DataFrame,
    full_features: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    calibrated, calibration = _calibrated_primary(
        predictions, list(config["modeling"]["calibration_methods"])
    )
    policy = build_recall_first_policy_table(
        calibrated, [float(config["decision_policy"]["target_recall_within_each_sector"])]
    ).iloc[0]
    thresholds = {
        "Consumer Discretionary": float(policy["consumer_threshold"]),
        "Utilities": float(policy["utility_threshold"]),
    }
    calibrated["threshold"] = calibrated["sector"].map(thresholds)
    calibrated["alert"] = calibrated["probability"] >= calibrated["threshold"]
    calibrated["horizon_quarters"] = horizon
    lead = _first_breach_lead(full_features, horizon)
    lead_frame = full_features[["decision_key"]].copy()
    lead_frame["warning_lead_quarters"] = lead
    calibrated = calibrated.merge(lead_frame, on="decision_key", how="left", validate="one_to_one")
    labels = calibrated["deterioration_label"].astype(int)
    scores = calibrated["probability"].astype(float)
    decomposition = brier_decomposition(
        labels.to_numpy(), np.asarray(scores.to_numpy(), dtype=np.float64)
    )
    rows: list[dict[str, Any]] = []
    for sector, group in [("Overall", calibrated), *calibrated.groupby("sector")]:
        sector_labels = group["deterioration_label"].astype(int)
        sector_alerts = group["alert"]
        tp = int((sector_alerts & sector_labels.eq(1)).sum())
        rows.append(
            {
                "horizon_quarters": horizon,
                "sector": sector,
                "evaluated_company_quarters": len(group),
                "positive_company_quarters": int(sector_labels.sum()),
                "event_prevalence": float(sector_labels.mean()),
                "PR_AUC": float(average_precision_score(sector_labels, group["probability"])),
                "recall_at_80pct_policy": tp / int(sector_labels.sum()),
                "precision_at_80pct_policy": tp / int(sector_alerts.sum()),
                "alert_rate_at_80pct_policy": float(sector_alerts.mean()),
                "Brier_score": float(brier_score_loss(sector_labels, group["probability"])),
                "expected_calibration_error": _expected_calibration_error(
                    sector_labels, group["probability"]
                ),
                "median_warning_lead_quarters": float(
                    group.loc[
                        group["alert"] & sector_labels.eq(1),
                        "warning_lead_quarters",
                    ]
                    .dropna()
                    .astype(float)
                    .median()
                ),
            }
        )
    details = {
        "horizon_quarters": horizon,
        "calibration_method": calibration["calibration_method"],
        "calibration_scope": calibration["calibration_scope"],
        "calibration_reliability": decomposition["reliability"],
        **policy.to_dict(),
    }
    return pd.DataFrame(rows), calibrated, details


def _metric_vector(group: pd.DataFrame) -> dict[str, float]:
    labels = group["deterioration_label"].astype(int)
    alerts = group["alert"].astype(bool)
    true_positive = int((alerts & labels.eq(1)).sum())
    leads = group.loc[alerts & labels.eq(1), "warning_lead_quarters"].dropna().astype(float)
    return {
        "event_prevalence": float(labels.mean()),
        "PR_AUC": float(average_precision_score(labels, group["probability"])),
        "recall": true_positive / int(labels.sum()),
        "precision": true_positive / int(alerts.sum()),
        "alert_rate": float(alerts.mean()),
        "Brier_score": float(brier_score_loss(labels, group["probability"])),
        "median_warning_lead_quarters": float(leads.median()),
    }


def _clustered_horizon_differences(
    predictions: pd.DataFrame, *, repetitions: int, seed: int
) -> pd.DataFrame:
    """Bootstrap whole issuers and report two-quarter minus four-quarter differences."""

    common_keys = set(predictions.loc[predictions["horizon_quarters"].eq(2), "decision_key"]) & set(
        predictions.loc[predictions["horizon_quarters"].eq(4), "decision_key"]
    )
    data = predictions.loc[predictions["decision_key"].isin(common_keys)].copy()
    companies = data["cik"].unique()
    groups = {cik: group for cik, group in data.groupby("cik")}
    rng = np.random.default_rng(seed)
    estimates: dict[str, list[float]] = {}
    for _ in range(repetitions):
        sampled = rng.choice(companies, size=len(companies), replace=True)
        replicate = pd.concat([groups[cik] for cik in sampled], ignore_index=True)
        by_horizon = {
            horizon: _metric_vector(group)
            for horizon, group in replicate.groupby("horizon_quarters")
        }
        for metric in by_horizon[2]:
            estimates.setdefault(metric, []).append(by_horizon[2][metric] - by_horizon[4][metric])
    point = {horizon: _metric_vector(group) for horizon, group in data.groupby("horizon_quarters")}
    rows = []
    for metric, values in estimates.items():
        finite = np.asarray(values, dtype=float)
        finite = finite[np.isfinite(finite)]
        rows.append(
            {
                "metric": metric,
                "difference_2q_minus_4q": point[2][metric] - point[4][metric],
                "clustered_95pct_lower": float(np.quantile(finite, 0.025)),
                "clustered_95pct_upper": float(np.quantile(finite, 0.975)),
                "bootstrap_repetitions": repetitions,
                "cluster_unit": "company",
            }
        )
    return pd.DataFrame(rows)


def _format_value(value: Any, *, percent: bool = False) -> str:
    if pd.isna(value):
        return "not available"
    return f"{float(value):.1%}" if percent else f"{float(value):.2f}"


def _build_company_cases(
    predictions: pd.DataFrame, features: pd.DataFrame, reports: Path
) -> pd.DataFrame:
    primary = predictions.loc[predictions["horizon_quarters"].eq(4)].copy()
    primary["case_type"] = np.select(
        [
            primary["alert"] & primary["deterioration_label"].eq(1),
            primary["alert"] & primary["deterioration_label"].eq(0),
            ~primary["alert"] & primary["deterioration_label"].eq(1),
        ],
        ["true_positive", "false_positive", "missed_deterioration"],
        default="true_negative",
    )
    selections = {
        "true_positive": primary.loc[primary["case_type"].eq("true_positive")]
        .sort_values("probability", ascending=False)
        .head(1),
        "false_positive": primary.loc[primary["case_type"].eq("false_positive")]
        .sort_values("probability", ascending=False)
        .head(1),
        "missed_deterioration": primary.loc[primary["case_type"].eq("missed_deterioration")]
        .assign(distance=lambda x: x["threshold"] - x["probability"])
        .sort_values("distance")
        .head(1),
    }
    reference = features.loc[features["decision_at"] < pd.Timestamp("2023-01-01")]
    joined = pd.concat(selections.values(), ignore_index=True).merge(
        features,
        on="decision_key",
        how="left",
        validate="one_to_one",
        suffixes=("", "_feature"),
    )
    rows = []
    for _, row in joined.iterrows():
        reasons = [
            reason
            for reason in company_reason_codes(row, reference, maximum_reasons=5)
            if reason["feature"] != "filing_delay_days"
        ][:4]
        case_type = str(row["case_type"])
        if case_type == "true_positive":
            usefulness = (
                "Useful early-review alert: the subsequent coverage outcome met the "
                "deterioration rule."
            )
            error_reason = (
                "Not an error; the available financial signals ranked this event above "
                "its sector threshold."
            )
        elif case_type == "false_positive":
            usefulness = (
                "Potentially useful as a precautionary review, but it consumed capacity "
                "without a qualifying four-quarter event."
            )
            error_reason = (
                "Weak contemporaneous signals resembled deterioration, but future "
                "coverage did not satisfy both the level and decline rules."
            )
        else:
            usefulness = (
                "Not useful operationally because the deterioration was missed at the "
                "selected threshold."
            )
            error_reason = (
                "The observed predictors produced a score just below the sector cutoff; "
                "the later coverage decline was not strong enough in the available "
                "signals to trigger review."
            )
        rows.append(
            {
                "case_type": case_type,
                "company_name": row.get("company_name", ""),
                "ticker": row.get("ticker", ""),
                "sector": row["sector"],
                "decision_at": row["decision_at"],
                "probability": row["probability"],
                "sector_threshold": row["threshold"],
                "interest_coverage_ttm": row.get("interest_coverage_ttm"),
                "interest_coverage_trend_4q": row.get("interest_coverage_ttm_trend_4q"),
                "free_cash_flow_margin_ttm": row.get("free_cash_flow_margin_ttm"),
                "operating_margin_ttm": row.get("operating_margin_ttm"),
                "total_debt_to_assets": row.get("total_debt_to_assets"),
                "future_minimum_interest_coverage": row.get("future_minimum_interest_coverage"),
                "warning_lead_quarters": row.get("warning_lead_quarters"),
                "reason_codes_json": json.dumps(reasons),
                "analyst_usefulness": usefulness,
                "result_explanation": error_reason,
            }
        )
    cases = pd.DataFrame(rows)
    cases.to_csv(reports / "phase2_company_case_studies.csv", index=False)
    sections = ["# Phase 2 Company Case Studies", ""]
    for _, row in cases.iterrows():
        title = str(row["case_type"]).replace("_", " ").title()
        sections.extend(
            [
                f"## {title}: {row['company_name']} ({row['ticker']})",
                "",
                f"At the {pd.Timestamp(row['decision_at']).date()} decision point, the "
                "model assigned "
                f"a probability of {row['probability']:.1%} against a "
                f"{row['sector_threshold']:.1%} "
                f"{row['sector']} threshold.",
                "",
                "The available statements showed interest coverage of "
                f"{_format_value(row['interest_coverage_ttm'])}, free-cash-flow margin of "
                f"{_format_value(row['free_cash_flow_margin_ttm'], percent=True)}, "
                "operating margin of "
                f"{_format_value(row['operating_margin_ttm'], percent=True)}, and debt/assets of "
                f"{_format_value(row['total_debt_to_assets'], percent=True)}. The "
                "subsequent minimum "
                f"coverage in the four-quarter outcome window was "
                f"{_format_value(row['future_minimum_interest_coverage'])}.",
                "",
                f"**Analyst value.** {row['analyst_usefulness']}",
                "",
                f"**Why this result occurred.** {row['result_explanation']}",
                "",
            ]
        )
    (reports / "phase2_company_case_studies.md").write_text("\n".join(sections), encoding="utf-8")
    return cases


def run_stage_28() -> dict[str, Any]:
    """Run a paired, preregistered horizon sensitivity analysis on real data."""

    root = repository_root()
    processed = root / "data" / "processed"
    reports = root / "reports" / "generated"
    config = read_yaml(root / "configs" / "phase2.yml")
    panel = pd.read_parquet(processed / "phase2_point_in_time_panel.parquet")
    assignments = pd.read_parquet(processed / "phase2_temporal_assignments.parquet")
    horizon_features = {h: _features_for_horizon(panel, h) for h in (2, 4)}

    eligibility_rows = []
    for horizon, features in horizon_features.items():
        mature = features.loc[features["deterioration_label"].notna()]
        for sector, group in [("Overall", mature), *mature.groupby("sector")]:
            eligibility_rows.append(
                {
                    "horizon_quarters": horizon,
                    "sector": sector,
                    "eligible_company_quarters": len(group),
                    "eligible_companies": group["cik"].nunique(),
                    "positive_company_quarters": int(group["deterioration_label"].sum()),
                    "event_prevalence": float(group["deterioration_label"].mean()),
                }
            )
    eligibility = pd.DataFrame(eligibility_rows)
    eligibility.to_csv(reports / "phase2_horizon_eligibility_and_prevalence.csv", index=False)

    common_keys = set(
        horizon_features[2].loc[horizon_features[2]["deterioration_label"].notna(), "decision_key"]
    ) & set(
        horizon_features[4].loc[horizon_features[4]["deterioration_label"].notna(), "decision_key"]
    )
    paired_assignments = assignments.loc[assignments["decision_key"].isin(common_keys)].copy()
    all_predictions = []
    all_metrics = []
    policy_rows = []
    feature_rows = []
    for horizon in (4, 2):
        features = (
            horizon_features[horizon]
            .loc[horizon_features[horizon]["decision_key"].isin(common_keys)]
            .copy()
        )
        candidates = [
            feature for feature in INTERPRETABLE_CANDIDATE_FEATURES if feature in features
        ]
        selected_by_fold, evidence = select_features_temporally(
            features, paired_assignments, candidates, config["modeling"]
        )
        raw, _ = run_nested_logistic_architectures(
            features,
            paired_assignments,
            numeric_features=candidates,
            categorical_features=["sector", "industry"],
            config=config["modeling"],
            selected_features_by_fold=selected_by_fold,
        )
        raw["horizon_quarters"] = horizon
        raw["feature_increment"] = "temporally_selected_features"
        metrics, calibrated, details = _summarize_horizon(
            horizon, raw, horizon_features[horizon], config
        )
        evidence["horizon_quarters"] = horizon
        all_predictions.append(calibrated)
        all_metrics.append(metrics)
        policy_rows.append(details)
        feature_rows.append(evidence)

    comparison = pd.concat(all_metrics, ignore_index=True)
    predictions = pd.concat(all_predictions, ignore_index=True)
    comparison.to_csv(reports / "phase2_horizon_comparison.csv", index=False)
    predictions.to_parquet(processed / "phase2_horizon_oof_predictions.parquet", index=False)
    pd.DataFrame(policy_rows).to_csv(reports / "phase2_horizon_policy_comparison.csv", index=False)
    pd.concat(feature_rows, ignore_index=True).to_csv(
        reports / "phase2_horizon_feature_selection_evidence.csv", index=False
    )
    differences = _clustered_horizon_differences(
        predictions,
        repetitions=int(config["uncertainty"]["bootstrap_repetitions"]),
        seed=int(config["uncertainty"]["random_seed"]),
    )
    differences.to_csv(reports / "phase2_horizon_clustered_differences.csv", index=False)
    cases = _build_company_cases(predictions, horizon_features[4], reports)
    result = {
        "status": "complete",
        "design": "paired_expanding_window_sensitivity",
        "primary_horizon_quarters": 4,
        "secondary_horizon_quarters": 2,
        "paired_company_quarters": len(common_keys),
        "evaluated_prediction_rows": len(predictions),
        "company_case_studies": len(cases),
        "final_future_test_evaluated": False,
        "synthetic_data_used": False,
    }
    (reports / "stage28_summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result
