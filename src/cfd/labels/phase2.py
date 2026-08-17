"""Preregistered Phase 2 label sensitivity analyses."""

from __future__ import annotations

from itertools import product
from typing import Any

import numpy as np
import pandas as pd

from cfd.evaluation.phase2 import add_episode_ids
from cfd.labels.deterioration import make_deterioration_label


def registered_coverage_labels(panel: pd.DataFrame, config: dict[str, Any]) -> dict[str, pd.Series]:
    """Build every registered coverage label without using model performance."""

    sensitivity = config["label_sensitivity"]
    decline = float(sensitivity["benchmark"]["relative_coverage_decline"])
    labels: dict[str, pd.Series] = {}
    for horizon, threshold in product(
        sensitivity["registered_horizons_quarters"],
        sensitivity["registered_coverage_multiples"],
    ):
        name = f"coverage_h{int(horizon)}_threshold_{float(threshold):.1f}"
        labels[name] = make_deterioration_label(
            panel,
            horizon=int(horizon),
            absolute_threshold=float(threshold),
            relative_decline=decline,
        )
    return labels


def make_multikpi_deterioration_label(panel: pd.DataFrame, config: dict[str, Any]) -> pd.Series:
    """Require two of three intuitive forms of future financial weakening.

    Components are: the frozen coverage rule, negative free-cash-flow margin,
    and an absolute increase in debt/assets. The rule is a sensitivity outcome,
    not a candidate selected because it improves a model score.
    """

    sensitivity = config["label_sensitivity"]
    benchmark = sensitivity["benchmark"]
    rule = sensitivity["multi_kpi_rule"]
    coverage_label = make_deterioration_label(
        panel,
        horizon=int(benchmark["horizon_quarters"]),
        absolute_threshold=float(benchmark["coverage_multiple"]),
        relative_decline=float(benchmark["relative_coverage_decline"]),
    )
    ordered = panel.sort_values(["cik", "period_end"])
    output = pd.Series(pd.NA, index=panel.index, dtype="Int8")
    horizon = int(benchmark["horizon_quarters"])
    for _, company in ordered.groupby("cik", sort=False):
        for position, index in enumerate(company.index):
            future = company.iloc[position + 1 : position + horizon + 1]
            current_leverage = company.loc[index, "total_debt_to_assets"]
            required = [
                "free_cash_flow_margin_ttm",
                "total_debt_to_assets",
            ]
            if (
                len(future) < horizon
                or pd.isna(coverage_label.loc[index])
                or pd.isna(current_leverage)
                or future[required].isna().any().any()
            ):
                continue
            negative_fcf = bool(
                future["free_cash_flow_margin_ttm"].min()
                < float(rule["negative_fcf_margin_threshold"])
            )
            leverage_rise = bool(
                future["total_debt_to_assets"].max() - float(current_leverage)
                >= float(rule["leverage_increase_threshold"])
            )
            components = int(coverage_label.loc[index]) + int(negative_fcf) + int(leverage_rise)
            output.loc[index] = int(components >= int(rule["components_required"]))
    return output


def label_sensitivity_summary(panel: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Report row prevalence and distinct episodes for each registered outcome."""

    candidates = registered_coverage_labels(panel, config)
    candidates["multi_kpi_two_of_three"] = make_multikpi_deterioration_label(panel, config)
    rows: list[dict[str, Any]] = []
    for label_name, labels in candidates.items():
        labeled = panel[["cik", "decision_at", "sector"]].copy()
        labeled["deterioration_label"] = labels
        for sector_name, sector_rows in [("Overall", labeled), *labeled.groupby("sector")]:
            mature = sector_rows.dropna(subset=["deterioration_label"])
            episodes = add_episode_ids(mature)
            rows.append(
                {
                    "label": label_name,
                    "sector": sector_name,
                    "mature_company_quarters": len(mature),
                    "positive_company_quarters": int(mature["deterioration_label"].sum()),
                    "prevalence": float(mature["deterioration_label"].mean())
                    if len(mature)
                    else np.nan,
                    "distinct_episodes": int(episodes["deterioration_episode_start"].sum()),
                    "selected_using_model_performance": False,
                }
            )
    return pd.DataFrame(rows)
