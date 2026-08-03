"""Publication-grade Stage 13-15 model diagnostics using the project-wide theme."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import seaborn as sns  # type: ignore[import-untyped]
from matplotlib import pyplot as plt
from sklearn.calibration import calibration_curve  # type: ignore[import-untyped]
from sklearn.metrics import average_precision_score  # type: ignore[import-untyped]

from cfd.analysis.eda import (
    KPI_LABELS,
    _finish_axes,
    _save_figure,
    apply_publication_theme,
)
from cfd.config import repository_root

MODEL_LABELS = {
    "random_walk": "Random walk",
    "random_walk_drift": "Random walk + drift",
    "local_level": "Local level",
    "local_linear_trend": "Local linear trend",
    "regression_dlm": "Regression DLM",
    "logistic_regression": "Logistic regression",
    "gradient_boosted_trees": "Gradient-boosted trees",
}
INCREMENT_LABELS = {
    "current_fundamentals": "Current",
    "historical_and_peer": "+ history & peers",
    "forecast_interest_coverage": "+ coverage forecast",
    "all_forecasts": "+ all forecasts",
    "macro_and_interactions": "+ macro & interactions",
}


def _write_manifest(output: Path, style: dict[str, Any], figures: list[dict[str, Any]]) -> None:
    (output / "figure_manifest.json").write_text(
        json.dumps(
            {
                "theme_version": style["version"],
                "title_prefix": style["title_prefix"],
                "figures": figures,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def plot_stage13_results(metrics: pd.DataFrame) -> dict[str, Any]:
    style = apply_publication_theme()
    output = repository_root() / "reports" / "figures" / "stage13"
    output.mkdir(parents=True, exist_ok=True)
    colors = sns.color_palette("colorblind", n_colors=metrics["model"].nunique())
    model_order = list(MODEL_LABELS)[:5]
    display = metrics.copy()
    display["Model"] = display["model"].map(MODEL_LABELS)
    figures: list[dict[str, Any]] = []

    figure, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    for axis, kpi in zip(axes, KPI_LABELS, strict=True):
        subset = display.loc[display["kpi"] == kpi]
        sns.barplot(
            data=subset,
            x="horizon",
            y="RMSE",
            hue="Model",
            hue_order=[MODEL_LABELS[value] for value in model_order],
            palette=colors,
            ax=axis,
        )
        axis.set_title(KPI_LABELS[kpi])
        axis.set_xlabel("Forecast horizon (quarters)")
        axis.set_ylabel("RMSE")
        if axis is not axes[-1] and axis.legend_ is not None:
            axis.legend_.remove()
        _finish_axes(axis)
    axes[-1].legend(title=None, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    figures.append(
        _save_figure(
            figure,
            slug="01-forecast-rmse-by-kpi-and-horizon",
            title="Forecast RMSE by KPI and horizon",
            description="All five candidates are compared at identical company-level origins.",
            output_directory=output,
            style=style,
        )
    )

    figure, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    for axis, kpi in zip(axes, KPI_LABELS, strict=True):
        subset = display.loc[display["kpi"] == kpi]
        sns.lineplot(
            data=subset,
            x="horizon",
            y="interval_coverage",
            hue="Model",
            hue_order=[MODEL_LABELS[value] for value in model_order],
            palette=colors,
            marker="o",
            ax=axis,
        )
        axis.axhline(0.95, color=style["neutral_colors"]["secondary"], linestyle="--")
        axis.set_ylim(0, 1.02)
        axis.set_title(KPI_LABELS[kpi])
        axis.set_xlabel("Forecast horizon (quarters)")
        axis.set_ylabel("95% interval coverage")
        if axis is not axes[-1] and axis.legend_ is not None:
            axis.legend_.remove()
        _finish_axes(axis)
    axes[-1].legend(title=None, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    figures.append(
        _save_figure(
            figure,
            slug="02-forecast-interval-coverage",
            title="Forecast interval coverage",
            description="Empirical coverage is shown against the nominal 95% reference.",
            output_directory=output,
            style=style,
        )
    )
    _write_manifest(output, style, figures)
    return {"figures": len(figures), "exported_files": len(figures) * 2, "directory": str(output)}


def plot_stage14_results(predictions: pd.DataFrame) -> dict[str, Any]:
    style = apply_publication_theme()
    output = repository_root() / "reports" / "figures" / "stage14"
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for (model, increment), group in predictions.groupby(["model", "feature_increment"]):
        rows.append(
            {
                "Model": MODEL_LABELS[str(model)],
                "Feature increment": INCREMENT_LABELS[str(increment)],
                "PR-AUC": average_precision_score(
                    group["deterioration_label"].astype(int), group["probability"]
                ),
            }
        )
    comparison = pd.DataFrame(rows)
    order = list(INCREMENT_LABELS.values())
    figure, axis = plt.subplots(figsize=(11, 5.5))
    sns.lineplot(
        data=comparison,
        x="Feature increment",
        y="PR-AUC",
        hue="Model",
        marker="o",
        linewidth=2.2,
        palette=[style["neutral_colors"]["primary"], style["neutral_colors"]["positive"]],
        sort=False,
        ax=axis,
    )
    axis.set_xticks(range(len(order)), labels=order, rotation=18, ha="right")
    axis.set_ylabel("Out-of-fold PR-AUC")
    axis.set_xlabel("")
    _finish_axes(axis)
    figure_record = _save_figure(
        figure,
        slug="01-classifier-feature-increment-pr-auc",
        title="Classifier value by feature increment",
        description=(
            "Out-of-fold PR-AUC isolates the incremental value of forecasts and macro context."
        ),
        output_directory=output,
        style=style,
    )
    _write_manifest(output, style, [figure_record])
    return {"figures": 1, "exported_files": 2, "directory": str(output)}


def plot_stage15_results(
    oof_predictions: pd.DataFrame,
    holdout_predictions: pd.DataFrame,
    holdout_metrics: pd.DataFrame,
    importance: pd.DataFrame,
    champion_model: str,
    champion_increment: str,
) -> dict[str, Any]:
    style = apply_publication_theme()
    output = repository_root() / "reports" / "figures" / "stage15"
    output.mkdir(parents=True, exist_ok=True)
    figures: list[dict[str, Any]] = []
    champion_oof = oof_predictions.loc[
        (oof_predictions["model"] == champion_model)
        & (oof_predictions["feature_increment"] == champion_increment)
    ]

    figure, axis = plt.subplots(figsize=(7.5, 6))
    for label, frame, color in [
        ("Development OOF", champion_oof, style["neutral_colors"]["primary"]),
        ("Locked holdout", holdout_predictions, style["neutral_colors"]["positive"]),
    ]:
        observed, predicted = calibration_curve(
            frame["deterioration_label"].astype(int), frame["probability"], n_bins=8
        )
        axis.plot(predicted, observed, marker="o", linewidth=2, label=label, color=color)
    axis.plot([0, 1], [0, 1], linestyle="--", color=style["neutral_colors"]["secondary"])
    axis.set_xlabel("Mean predicted probability")
    axis.set_ylabel("Observed deterioration rate")
    axis.legend()
    _finish_axes(axis)
    figures.append(
        _save_figure(
            figure,
            slug="01-champion-calibration",
            title="Champion probability calibration",
            description=(
                "Development out-of-fold and one-time locked-holdout calibration are separated."
            ),
            output_directory=output,
            style=style,
        )
    )

    metrics_long = holdout_metrics.melt(
        id_vars="sector",
        value_vars=["PR_AUC", "recall", "precision"],
        var_name="Metric",
        value_name="Value",
    )
    metrics_long["Metric"] = metrics_long["Metric"].map(
        {"PR_AUC": "PR-AUC", "recall": "Recall", "precision": "Precision"}
    )
    figure, axes = plt.subplots(1, 2, figsize=(13, 5.5), gridspec_kw={"width_ratios": [3, 1]})
    palette = {
        "Overall": style["neutral_colors"]["primary"],
        **style["sector_colors"],
    }
    sns.barplot(data=metrics_long, x="Metric", y="Value", hue="sector", palette=palette, ax=axes[0])
    lift = holdout_metrics.copy()
    lift["display_sector"] = lift["sector"].map(
        {
            "Overall": "Overall",
            "Consumer Discretionary": "Consumer\nDiscretionary",
            "Utilities": "Utilities",
        }
    )
    sns.barplot(
        data=lift,
        x="display_sector",
        y="top_decile_lift",
        hue="sector",
        palette=palette,
        legend=False,
        ax=axes[1],
    )
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Holdout score")
    axes[0].set_ylim(0, 1)
    axes[0].legend(title=None, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Top-decile lift")
    axes[1].tick_params(axis="x", rotation=0)
    for axis in axes:
        _finish_axes(axis)
    figures.append(
        _save_figure(
            figure,
            slug="02-holdout-performance-by-sector",
            title="Locked-holdout performance by sector",
            description="Sector slices expose stability and asymmetric alert quality.",
            output_directory=output,
            style=style,
        )
    )

    top = importance.head(15).copy()
    top["display_feature"] = (
        top["feature"]
        .str.replace(r"^(numeric|categorical)__", "", regex=True)
        .str.replace("missingindicator_", "Missing: ", regex=False)
        .str.replace("_", " ", regex=False)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    top = top.sort_values("absolute_importance")
    figure, axis = plt.subplots(figsize=(10, 7))
    sns.barplot(
        data=top,
        y="display_feature",
        x="absolute_importance",
        color=style["neutral_colors"]["positive"],
        ax=axis,
    )
    axis.set_xlabel("Absolute model importance")
    axis.set_ylabel("")
    _finish_axes(axis)
    figures.append(
        _save_figure(
            figure,
            slug="03-champion-feature-importance",
            title="Champion feature importance",
            description="Importance is descriptive and does not imply causal effect.",
            output_directory=output,
            style=style,
        )
    )
    _write_manifest(output, style, figures)
    return {"figures": len(figures), "exported_files": len(figures) * 2, "directory": str(output)}


def run_model_result_plots() -> dict[str, Any]:
    root = repository_root()
    processed = root / "data" / "processed"
    reports = root / "reports" / "generated"
    selection = json.loads((reports / "champion_selection_frozen.json").read_text())
    return {
        "stage13": plot_stage13_results(pd.read_csv(reports / "forecast_model_metrics.csv")),
        "stage14": plot_stage14_results(
            pd.read_parquet(processed / "classifier_oof_predictions.parquet")
        ),
        "stage15": plot_stage15_results(
            pd.read_parquet(processed / "classifier_oof_predictions.parquet"),
            pd.read_parquet(processed / "final_holdout_predictions.parquet"),
            pd.read_csv(reports / "final_holdout_metrics.csv"),
            pd.read_csv(reports / "champion_feature_importance.csv"),
            selection["model"],
            selection["feature_increment"],
        ),
    }
