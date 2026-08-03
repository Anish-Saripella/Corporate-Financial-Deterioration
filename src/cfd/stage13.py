"""Stage 13 rolling KPI forecasting, selection, and feature generation."""

from __future__ import annotations

import json
from typing import Any

import duckdb
import pandas as pd

from cfd.config import read_yaml, repository_root
from cfd.forecasting.evaluation import (
    build_forecast_backtest,
    generate_forecast_features,
    select_forecast_champions,
    summarize_forecasts,
)


def run_stage_13() -> dict[str, Any]:
    root = repository_root()
    processed = root / "data" / "processed"
    reports = root / "reports" / "generated"
    config = read_yaml(root / "configs" / "modeling.yml")["forecasting"]
    panel = pd.read_parquet(processed / "labeled_company_quarters.parquet")
    fold_summary = pd.read_csv(reports / "temporal_fold_summary.csv")
    predictions = build_forecast_backtest(panel, fold_summary, config)
    metrics = summarize_forecasts(predictions)
    selection = select_forecast_champions(metrics)
    forecast_features = generate_forecast_features(panel, selection, config)
    if forecast_features["decision_key"].duplicated().any():
        raise ValueError("Forecast features contain duplicate decision keys")
    if (
        forecast_features["forecast_feature_available_at"]
        > panel.set_index("decision_key")
        .loc[forecast_features["decision_key"], "decision_at"]
        .to_numpy()
    ).any():
        raise ValueError("Forecast feature availability exceeds its decision time")
    predictions.to_parquet(processed / "forecast_backtest_predictions.parquet", index=False)
    forecast_features.to_parquet(processed / "forecast_features.parquet", index=False)
    partition_root = processed / "partitions" / "forecast_backtest_predictions"
    for (fold_id, horizon), group in predictions.groupby(["fold_id", "horizon"]):
        directory = partition_root / f"fold_id={fold_id}" / f"horizon={int(str(horizon))}"
        directory.mkdir(parents=True, exist_ok=True)
        group.to_parquet(directory / "part.parquet", index=False)
    metrics.to_csv(reports / "forecast_model_metrics.csv", index=False)
    selection.to_csv(reports / "forecast_model_selection.csv", index=False)
    with duckdb.connect(str(processed / "cfd.duckdb")) as connection:
        for table, filename in {
            "forecast_backtest_predictions": "forecast_backtest_predictions.parquet",
            "forecast_features": "forecast_features.parquet",
        }.items():
            location = str(processed / filename).replace("'", "''")
            connection.execute(
                f"CREATE OR REPLACE TABLE marts.{table} AS SELECT * FROM read_parquet('{location}')"
            )
    champions = selection.loc[selection["selected"], ["kpi", "horizon", "model", "RMSE"]]
    result = {
        "status": "complete",
        "forecasting_version": "phase1-modeling-v1",
        "backtest_predictions": len(predictions),
        "forecast_feature_rows": len(forecast_features),
        "models_compared": sorted(predictions["model"].unique().tolist()),
        "horizons": sorted(predictions["horizon"].unique().astype(int).tolist()),
        "champions": champions.to_dict("records"),
        "classifier_forecast_feature_model": config["classifier_feature_model"],
        "classifier_feature_model_selection": config["classifier_feature_model_selection"],
        "holdout_used_for_selection": False,
    }
    (reports / "stage13_summary.json").write_text(
        json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return result
