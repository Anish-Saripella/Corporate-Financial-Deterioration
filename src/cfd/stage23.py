"""Stage 23: Phase 2 feature ablation and nested temporal model comparison."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from cfd.config import read_yaml, repository_root
from cfd.evaluation.temporal import build_expanding_window_splits
from cfd.features.engineering import engineer_historical_features
from cfd.features.phase2 import engineer_phase2_financial_features
from cfd.labels.deterioration import deterioration_diagnostics
from cfd.labels.phase2 import label_sensitivity_summary
from cfd.modeling.calibration import cross_fitted_temporal_calibration
from cfd.modeling.feature_selection import select_features_temporally
from cfd.modeling.phase2 import run_nested_logistic_architectures

CORE_FEATURES = [
    "interest_coverage_ttm",
    "free_cash_flow_margin_ttm",
    "total_debt_to_assets",
    "operating_margin_ttm",
    "current_ratio",
    "cash_to_assets",
]
INTERPRETABLE_CANDIDATE_FEATURES = [
    *CORE_FEATURES,
    "refinancing_gap_to_assets",
    "working_capital_to_assets",
    "capital_expenditure_to_revenue",
    "cash_flow_conversion",
    "revenue_growth_yoy",
    "asset_turnover",
    "net_income_margin_ttm",
    "interest_coverage_ttm_yoy_change",
    "free_cash_flow_margin_ttm_yoy_change",
    "total_debt_to_assets_yoy_change",
    "interest_coverage_ttm_volatility_4q",
    "free_cash_flow_margin_ttm_volatility_4q",
    "total_debt_to_assets_volatility_4q",
    "interest_coverage_ttm_trend_4q",
    "free_cash_flow_margin_ttm_trend_4q",
    "total_debt_to_assets_trend_4q",
    "interest_coverage_ttm_sector_percentile",
    "free_cash_flow_margin_ttm_sector_percentile",
    "total_debt_to_assets_sector_percentile",
]


def run_stage_23() -> dict[str, Any]:
    """Create real OOF predictions; never open or invent a final test period."""

    root = repository_root()
    processed = root / "data" / "processed"
    reports = root / "reports" / "generated"
    panel_path = processed / "phase2_point_in_time_panel.parquet"
    if not panel_path.exists():
        raise FileNotFoundError(f"Certified real Phase 2 panel is missing: {panel_path}")
    config = read_yaml(root / "configs" / "phase2.yml")
    panel = pd.read_parquet(panel_path)
    labeled = deterioration_diagnostics(panel)
    features = engineer_historical_features(labeled)
    features = engineer_phase2_financial_features(features)
    mature = features.loc[features["deterioration_label"].notna()].copy()
    if mature.empty:
        raise ValueError("Phase 2 panel contains no matured real deterioration outcomes")
    label_sensitivity_summary(panel, config).to_csv(
        reports / "phase2_label_sensitivity_summary.csv", index=False
    )
    development_end = (mature["decision_at"].max().to_period("Q") + 1).start_time
    assignments, locked, folds = build_expanding_window_splits(
        features,
        holdout_start=str(development_end.date()),
        minimum_training_quarters=int(
            config["evaluation_policy"]["minimum_outer_training_quarters"]
        ),
        validation_window_quarters=int(config["evaluation_policy"]["validation_window_quarters"]),
        step_quarters=int(config["evaluation_policy"]["step_quarters"]),
    )
    if not locked.empty:
        # These are immature/post-development rows, not a final performance test.
        locked["split"] = "OUTCOME_NOT_USED_FOR_DEVELOPMENT"
    selected_by_fold, feature_evidence = select_features_temporally(
        features,
        assignments,
        [feature for feature in INTERPRETABLE_CANDIDATE_FEATURES if feature in features],
        config["modeling"],
    )
    raw_predictions, selections = run_nested_logistic_architectures(
        features,
        assignments,
        numeric_features=INTERPRETABLE_CANDIDATE_FEATURES,
        categorical_features=["sector", "industry"],
        config=config["modeling"],
        selected_features_by_fold=selected_by_fold,
    )
    raw_predictions["feature_increment"] = "temporally_selected_features"
    selections["feature_increment"] = "temporally_selected_features"
    calibrated_frames: list[pd.DataFrame] = []
    for (_model, _increment), group in raw_predictions.groupby(
        ["model", "feature_increment"], sort=True
    ):
        for sector_specific in [False, True]:
            calibrated = cross_fitted_temporal_calibration(
                group,
                list(config["modeling"]["calibration_methods"]),
                sector_specific=sector_specific,
            )
            if not calibrated.empty:
                calibrated_frames.append(calibrated)
    calibrated_predictions = pd.concat(calibrated_frames, ignore_index=True)
    features.to_parquet(processed / "phase2_model_features.parquet", index=False)
    assignments.to_parquet(processed / "phase2_temporal_assignments.parquet", index=False)
    raw_predictions.to_parquet(processed / "phase2_oof_predictions.parquet", index=False)
    calibrated_predictions.to_parquet(
        processed / "phase2_calibrated_oof_predictions.parquet", index=False
    )
    selections.to_csv(reports / "phase2_nested_model_selection.csv", index=False)
    feature_evidence.to_csv(reports / "phase2_feature_selection_evidence.csv", index=False)
    latest_fold = sorted(selected_by_fold)[-1]
    feature_stability = (
        feature_evidence.groupby("feature", as_index=False)
        .agg(
            selected_folds=("selected", "sum"),
            evaluated_folds=("fold_id", "nunique"),
            mean_permutation_PR_AUC_loss=("mean_permutation_PR_AUC_loss", "mean"),
            mean_positive_permutation_share=("positive_permutation_share", "mean"),
        )
        .sort_values(
            ["selected_folds", "mean_permutation_PR_AUC_loss"],
            ascending=[False, False],
        )
    )
    feature_stability["selected_in_every_outer_training_fold"] = (
        feature_stability["selected_folds"] == feature_stability["evaluated_folds"]
    )
    feature_stability["latest_training_fold_recommendation"] = feature_stability["feature"].isin(
        selected_by_fold[latest_fold]
    )
    feature_stability.to_csv(reports / "phase2_feature_selection_stability.csv", index=False)
    pd.DataFrame(folds).to_csv(reports / "phase2_temporal_folds.csv", index=False)
    result = {
        "status": "complete",
        "modeling_version": "phase2-nested-temporal-v1",
        "issuers": int(features["cik"].nunique()),
        "outer_folds": len(folds),
        "architectures": sorted(raw_predictions["model"].unique().tolist()),
        "feature_increments": ["temporally_selected_features"],
        "selected_features_by_fold": selected_by_fold,
        "raw_oof_predictions": len(raw_predictions),
        "calibrated_oof_predictions": len(calibrated_predictions),
        "final_test_evaluated": False,
        "consumed_2023_plus_period_treated_as_development": True,
        "synthetic_data_used": False,
    }
    (reports / "stage23_summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result
