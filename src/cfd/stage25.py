"""Stage 25: Phase 2 KPI forecast ablation and interval recalibration."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from cfd.config import read_yaml, repository_root
from cfd.evaluation.temporal import build_expanding_window_splits
from cfd.forecasting.evaluation import (
    build_forecast_backtest,
    generate_forecast_features,
    select_forecast_champions,
    summarize_forecasts,
)
from cfd.forecasting.intervals import apply_empirical_intervals, fit_empirical_intervals
from cfd.labels.deterioration import deterioration_diagnostics


def run_stage_25() -> dict[str, Any]:
    """Compare real rolling forecasts and build optional classifier features."""

    root = repository_root()
    processed = root / "data" / "processed"
    reports = root / "reports" / "generated"
    panel_path = processed / "phase2_point_in_time_panel.parquet"
    if not panel_path.exists():
        raise FileNotFoundError(f"Certified real Phase 2 panel is missing: {panel_path}")
    panel = deterioration_diagnostics(pd.read_parquet(panel_path))
    phase2 = read_yaml(root / "configs" / "phase2.yml")
    forecast_config = read_yaml(root / "configs" / "modeling.yml")["forecasting"]
    mature = panel.loc[panel["deterioration_label"].notna()]
    development_end = (mature["decision_at"].max().to_period("Q") + 1).start_time
    _, _, folds = build_expanding_window_splits(
        panel,
        holdout_start=str(development_end.date()),
        minimum_training_quarters=int(
            phase2["evaluation_policy"]["minimum_outer_training_quarters"]
        ),
        validation_window_quarters=int(phase2["evaluation_policy"]["validation_window_quarters"]),
        step_quarters=int(phase2["evaluation_policy"]["step_quarters"]),
    )
    predictions = build_forecast_backtest(panel, pd.DataFrame(folds), forecast_config)
    metrics = summarize_forecasts(predictions)
    selection = select_forecast_champions(metrics)
    interval_calibration = fit_empirical_intervals(
        predictions,
        interval_level=float(forecast_config["interval_level"]),
        minimum_group_observations=30,
    )
    recalibrated = apply_empirical_intervals(predictions, interval_calibration)
    forecast_features = generate_forecast_features(panel, selection, forecast_config)
    predictions.to_parquet(processed / "phase2_forecast_backtest.parquet", index=False)
    recalibrated.to_parquet(
        processed / "phase2_forecast_backtest_recalibrated.parquet", index=False
    )
    forecast_features.to_parquet(processed / "phase2_forecast_features.parquet", index=False)
    metrics.to_csv(reports / "phase2_forecast_metrics.csv", index=False)
    selection.to_csv(reports / "phase2_forecast_selection.csv", index=False)
    interval_calibration.to_csv(reports / "phase2_forecast_interval_calibration.csv", index=False)
    coverage = recalibrated.groupby(["kpi", "sector", "horizon"], as_index=False).agg(
        empirical_interval_coverage=("interval_covered", "mean")
    )
    coverage.to_csv(reports / "phase2_forecast_interval_coverage.csv", index=False)
    result: dict[str, Any] = {
        "status": "complete",
        "forecasting_version": "phase2-empirical-intervals-v1",
        "backtest_predictions": len(predictions),
        "models": sorted(predictions["model"].unique().tolist()),
        "forecast_feature_rows": len(forecast_features),
        "interval_level": float(forecast_config["interval_level"]),
        "classifier_forecasts_are_optional_pending_ablation": True,
        "final_test_evaluated": False,
        "synthetic_data_used": False,
    }
    (reports / "stage25_summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result
