"""Stage 10 financial, sector, and time-series EDA with a uniform publication theme."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import matplotlib
import numpy as np
import pandas as pd
import seaborn as sns  # type: ignore[import-untyped]
from matplotlib import pyplot as plt
from matplotlib import ticker as mtick
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from cfd.config import read_yaml, repository_root
from cfd.panel import KPI_COLUMNS

matplotlib.use("Agg")

KPI_LABELS = {
    "interest_coverage_ttm": "Interest coverage (TTM)",
    "free_cash_flow_margin_ttm": "Free-cash-flow margin (TTM)",
    "total_debt_to_assets": "Total debt to assets",
}


def _style() -> dict[str, Any]:
    return read_yaml(repository_root() / "configs" / "plot_style.yml")


def apply_publication_theme() -> dict[str, Any]:
    style = _style()
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams.update(
        {
            "font.family": style["font_family"],
            "figure.facecolor": style["background"],
            "axes.facecolor": style["background"],
            "axes.edgecolor": style["grid_color"],
            "axes.labelcolor": style["text_color"],
            "text.color": style["text_color"],
            "xtick.color": style["text_color"],
            "ytick.color": style["text_color"],
            "grid.color": style["grid_color"],
            "grid.linewidth": 0.6,
            "axes.titleweight": "bold",
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "legend.frameon": False,
            "figure.dpi": 120,
            "savefig.dpi": int(style["dpi"]),
            "savefig.bbox": "tight",
        }
    )
    return style


def _uniform_title(style: dict[str, Any], title: str) -> str:
    return f"{style['title_prefix']} | {title}"


def _finish_axes(axis: Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="x", alpha=0.45)
    axis.grid(axis="y", alpha=0.25)


def _save_figure(
    figure: Figure,
    *,
    slug: str,
    title: str,
    description: str,
    output_directory: Path,
    style: dict[str, Any],
) -> dict[str, Any]:
    figure.suptitle(_uniform_title(style, title), x=0.01, ha="left", y=1.015, fontsize=14)
    figure.tight_layout()
    files: list[str] = []
    for extension in style["export_formats"]:
        destination = output_directory / f"{slug}.{extension}"
        figure.savefig(destination, format=extension, facecolor=style["background"])
        files.append(str(destination.relative_to(repository_root())))
    plt.close(figure)
    return {"slug": slug, "title": title, "description": description, "files": files}


def _display_bounds(series: pd.Series) -> tuple[float, float]:
    finite = series.replace([np.inf, -np.inf], np.nan).dropna()
    if finite.empty:
        return 0.0, 1.0
    return float(finite.quantile(0.01)), float(finite.quantile(0.99))


def time_series_diagnostics(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (cik, sector), company in panel.groupby(["cik", "sector"]):
        company = company.sort_values("decision_at")
        for kpi in KPI_COLUMNS:
            values = company[kpi].replace([np.inf, -np.inf], np.nan).dropna()
            if len(values) < 8:
                continue
            trend = values.rolling(4, min_periods=2).mean()
            noise = values - trend
            noise_variance = float(cast(Any, noise.var()))
            signal_variance = float(cast(Any, trend.var()))
            midpoint = len(values) // 2
            scale = max(float(values.std()), np.finfo(float).eps)
            rows.append(
                {
                    "cik": cik,
                    "sector": sector,
                    "kpi": kpi,
                    "observations": len(values),
                    "lag1_autocorrelation": float(values.autocorr(1)),
                    "signal_to_noise_ratio": signal_variance
                    / max(noise_variance, np.finfo(float).eps),
                    "skewness": float(cast(Any, values.skew())),
                    "excess_kurtosis": float(cast(Any, values.kurt())),
                    "mean_shift_standardized": float(
                        (values.iloc[midpoint:].mean() - values.iloc[:midpoint].mean()) / scale
                    ),
                }
            )
    return pd.DataFrame(rows)


def _plot_distributions(
    panel: pd.DataFrame, colors: dict[str, str]
) -> tuple[Figure, str, str, str]:
    figure, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    for axis, kpi in zip(axes, KPI_COLUMNS, strict=True):
        lower, upper = _display_bounds(panel[kpi])
        display = panel.loc[panel[kpi].between(lower, upper)]
        sns.boxplot(
            data=display,
            x="sector",
            y=kpi,
            hue="sector",
            palette=colors,
            showfliers=False,
            legend=False,
            ax=axis,
        )
        axis.set_title(KPI_LABELS[kpi])
        axis.set_xlabel("")
        axis.set_ylabel("Multiple" if kpi == "interest_coverage_ttm" else "Ratio")
        axis.tick_params(axis="x", rotation=12)
        _finish_axes(axis)
    return (
        figure,
        "01-kpi-distributions-by-sector",
        "KPI distributions by sector",
        "Boxplots use display-only 1st-99th percentile bounds; modeling values remain unchanged.",
    )


def _plot_trends(panel: pd.DataFrame, colors: dict[str, str]) -> tuple[Figure, str, str, str]:
    quarterly = panel.groupby(["calendar_quarter", "sector"])[KPI_COLUMNS].median().reset_index()
    quarterly["calendar_date"] = pd.PeriodIndex(
        quarterly["calendar_quarter"], freq="Q"
    ).to_timestamp()
    figure, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    for axis, kpi in zip(axes, KPI_COLUMNS, strict=True):
        for sector, group in quarterly.groupby("sector"):
            axis.plot(
                group["calendar_date"],
                group[kpi],
                label=sector,
                color=colors[str(sector)],
                linewidth=2,
            )
        axis.set_title(KPI_LABELS[kpi])
        axis.set_ylabel("Sector median")
        _finish_axes(axis)
    axes[0].legend(ncol=2, loc="best")
    axes[-1].set_xlabel("Fiscal period-end calendar quarter")
    return (
        figure,
        "02-sector-kpi-trajectories",
        "Sector KPI trajectories",
        "Quarterly sector medians show cyclical and defensive financial paths on a common "
        "timeline.",
    )


def _plot_events(panel: pd.DataFrame, colors: dict[str, str]) -> tuple[Figure, str, str, str]:
    event_rows = panel.groupby(["decision_year", "sector"], as_index=False).agg(
        episodes=("deterioration_episode_start", "sum"),
        labeled_rows=("deterioration_label", "count"),
    )
    event_rows["episode_rate"] = event_rows["episodes"] / event_rows["labeled_rows"].replace(
        0, np.nan
    )
    figure, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    sns.barplot(
        data=event_rows, x="decision_year", y="episodes", hue="sector", palette=colors, ax=axes[0]
    )
    sns.lineplot(
        data=event_rows,
        x="decision_year",
        y="episode_rate",
        hue="sector",
        palette=colors,
        marker="o",
        linewidth=2,
        ax=axes[1],
    )
    axes[0].set_title("Distinct deterioration episodes")
    axes[1].set_title("Episode rate per labeled row")
    axes[0].set_xlabel("Decision year")
    axes[0].set_ylabel("Distinct episodes")
    axes[1].set_xlabel("Decision year")
    axes[1].set_ylabel("Episode rate")
    axes[0].tick_params(axis="x", rotation=45)
    axes[1].tick_params(axis="x", rotation=45)
    for axis in axes:
        _finish_axes(axis)
    return (
        figure,
        "03-deterioration-episodes-over-time",
        "Deterioration episodes over time",
        "Distinct episodes use the frozen four-quarter cooldown and are reported separately "
        "by sector.",
    )


def _plot_coverage(panel: pd.DataFrame, colors: dict[str, str]) -> tuple[Figure, str, str, str]:
    long = panel.melt(
        id_vars=["sector"], value_vars=KPI_COLUMNS, var_name="kpi", value_name="value"
    )
    coverage = (
        long.assign(available=long["value"].notna())
        .groupby(["sector", "kpi"], as_index=False)["available"]
        .mean()
    )
    coverage["kpi_label"] = coverage["kpi"].map(KPI_LABELS)
    figure, axis = plt.subplots(figsize=(10, 5))
    sns.barplot(
        data=coverage,
        y="kpi_label",
        x="available",
        hue="sector",
        palette=colors,
        ax=axis,
    )
    axis.axvline(0.80, color="#64748B", linewidth=1.2, linestyle="--", label="80% gate")
    axis.set_xlim(0, 1)
    axis.set_xlabel("Available share of company-quarter rows")
    axis.set_ylabel("")
    axis.legend(title=None, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    _finish_axes(axis)
    return (
        figure,
        "04-certified-kpi-coverage",
        "Certified KPI coverage",
        "Aggregate availability complements the stricter company-level coverage and "
        "continuity gates.",
    )


def _plot_risk_map(panel: pd.DataFrame, colors: dict[str, str]) -> tuple[Figure, str, str, str]:
    lower_x, upper_x = _display_bounds(panel["total_debt_to_assets"])
    lower_y, upper_y = _display_bounds(panel["interest_coverage_ttm"])
    display = panel.loc[
        panel["total_debt_to_assets"].between(lower_x, upper_x)
        & panel["interest_coverage_ttm"].between(lower_y, upper_y)
    ]
    display = display.copy()
    display["Sector"] = display["sector"]
    display["Four-quarter outcome"] = display["deterioration_label"].map(
        {0: "No deterioration", 1: "Deterioration"}
    )
    figure, axis = plt.subplots(figsize=(10, 6))
    sns.scatterplot(
        data=display,
        x="total_debt_to_assets",
        y="interest_coverage_ttm",
        hue="Sector",
        style="Four-quarter outcome",
        palette=colors,
        alpha=0.62,
        s=42,
        ax=axis,
    )
    axis.axhline(1.5, color="#C2410C", linewidth=1.2, linestyle="--")
    axis.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0, decimals=0))
    axis.set_xlabel("Debt-to-assets ratio (%)")
    axis.set_ylabel("Interest coverage (TTM multiple, x)")
    _finish_axes(axis)
    return (
        figure,
        "05-leverage-and-interest-coverage-risk-map",
        "Leverage and interest-coverage risk map",
        "Each point combines leverage (debt as a percentage of assets) with debt-service "
        "capacity (operating income divided by interest expense, expressed as a multiple).",
    )


def _plot_industries(panel: pd.DataFrame, colors: dict[str, str]) -> tuple[Figure, str, str, str]:
    companies = panel[["cik", "sector", "industry"]].drop_duplicates()
    counts = companies.groupby(["industry", "sector"], as_index=False).size()
    counts = counts.sort_values("size")
    figure, axis = plt.subplots(figsize=(10, 7))
    sns.barplot(data=counts, y="industry", x="size", hue="sector", palette=colors, ax=axis)
    axis.set_xlabel("Certified companies")
    axis.set_ylabel("")
    _finish_axes(axis)
    return (
        figure,
        "06-certified-industry-composition",
        "Certified industry composition",
        "The final 30/30 sector design retains multiple industries instead of one dominant "
        "subsector.",
    )


def _plot_diagnostics(
    diagnostics: pd.DataFrame, colors: dict[str, str]
) -> tuple[Figure, str, str, str]:
    summary = diagnostics.groupby(["sector", "kpi"], as_index=False).agg(
        lag1_autocorrelation=("lag1_autocorrelation", "median"),
        signal_to_noise_ratio=("signal_to_noise_ratio", "median"),
    )
    summary["kpi_label"] = summary["kpi"].map(KPI_LABELS)
    figure, axes = plt.subplots(1, 2, figsize=(13, 5))
    sns.barplot(
        data=summary,
        y="kpi_label",
        x="lag1_autocorrelation",
        hue="sector",
        palette=colors,
        ax=axes[0],
    )
    sns.barplot(
        data=summary,
        y="kpi_label",
        x="signal_to_noise_ratio",
        hue="sector",
        palette=colors,
        ax=axes[1],
    )
    axes[0].set_title("Median lag-1 autocorrelation")
    axes[1].set_title("Median signal-to-noise ratio")
    axes[0].set_xlabel("Lag-1 autocorrelation")
    axes[1].set_xlabel("Signal-to-noise ratio")
    if axes[0].legend_ is not None:
        axes[0].legend_.remove()
    axes[1].legend(title=None, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    for axis in axes:
        axis.set_ylabel("")
        _finish_axes(axis)
    return (
        figure,
        "07-kpi-forecastability-diagnostics",
        "KPI forecastability diagnostics",
        "Persistence and signal-to-noise evidence informs the later baseline and state-space "
        "comparisons.",
    )


def _plot_macro_correlations(
    panel: pd.DataFrame, _colors: dict[str, str]
) -> tuple[Figure, str, str, str]:
    columns = [*KPI_COLUMNS, "DFF", "T10Y2Y", "BAA10Y", "UNRATE", "INDPRO", "RSAFS"]
    correlation_labels = {
        **KPI_LABELS,
        "DFF": "Federal funds rate",
        "T10Y2Y": "10Y-2Y Treasury spread",
        "BAA10Y": "BAA credit spread",
        "UNRATE": "Unemployment rate",
        "INDPRO": "Industrial production",
        "RSAFS": "Retail sales",
    }
    correlations = (
        panel[columns]
        .corr(method="spearman")
        .rename(index=correlation_labels, columns=correlation_labels)
    )
    figure, axis = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        correlations,
        cmap="vlag",
        center=0,
        vmin=-1,
        vmax=1,
        square=True,
        linewidths=0.5,
        annot=True,
        fmt=".2f",
        annot_kws={"fontsize": 8},
        ax=axis,
    )
    axis.set_xticklabels(axis.get_xticklabels(), rotation=40, ha="right")
    axis.set_yticklabels(axis.get_yticklabels(), rotation=0)
    return (
        figure,
        "08-kpi-macro-rank-correlations",
        "KPI and macro rank correlations",
        "Spearman correlations provide a restrained screen for macro inputs; they do not "
        "establish causality.",
    )


def run_eda(panel: pd.DataFrame) -> dict[str, Any]:
    root = repository_root()
    output = root / "reports" / "figures" / "stage10"
    output.mkdir(parents=True, exist_ok=True)
    style = apply_publication_theme()
    colors = {str(key): str(value) for key, value in style["sector_colors"].items()}
    diagnostics = time_series_diagnostics(panel)

    def diagnostics_builder(
        _frame: pd.DataFrame, palette: dict[str, str]
    ) -> tuple[Figure, str, str, str]:
        return _plot_diagnostics(diagnostics, palette)

    figure_builders: list[
        Callable[[pd.DataFrame, dict[str, str]], tuple[Figure, str, str, str]]
    ] = [
        _plot_distributions,
        _plot_trends,
        _plot_events,
        _plot_coverage,
        _plot_risk_map,
        _plot_industries,
        diagnostics_builder,
        _plot_macro_correlations,
    ]
    manifest: list[dict[str, Any]] = []
    for builder in figure_builders:
        figure, slug, title, description = builder(panel, colors)
        manifest.append(
            _save_figure(
                figure,
                slug=slug,
                title=title,
                description=description,
                output_directory=output,
                style=style,
            )
        )

    reports = root / "reports" / "generated"
    summary = panel.groupby("sector")[KPI_COLUMNS].describe().stack(future_stack=True)
    summary.to_csv(reports / "eda_financial_summary.csv")
    sector_group = panel.groupby("sector")[KPI_COLUMNS]
    missingness = (1 - sector_group.count().div(sector_group.size(), axis=0)).T
    missingness.to_csv(reports / "eda_kpi_missingness.csv")
    diagnostics.to_csv(reports / "eda_time_series_diagnostics.csv", index=False)
    (output / "figure_manifest.json").write_text(
        json.dumps(
            {
                "theme_version": style["version"],
                "title_prefix": style["title_prefix"],
                "display_only_clipping": "1st and 99th percentiles where noted",
                "figures": manifest,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "status": "complete",
        "theme_version": style["version"],
        "figures": len(manifest),
        "exported_files": sum(len(item["files"]) for item in manifest),
        "time_series_diagnostic_rows": len(diagnostics),
        "figure_directory": str(output),
    }
