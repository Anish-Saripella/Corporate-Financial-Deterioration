"""Stage 9 deterioration-label construction, audit, and freeze evidence."""

from __future__ import annotations

from typing import Any, cast

import pandas as pd

from cfd.config import read_yaml, repository_root
from cfd.labels.deterioration import deterioration_diagnostics


def _episode_counts(frame: pd.DataFrame) -> dict[str, Any]:
    labeled = frame["deterioration_label"].notna()
    return {
        "labeled_rows": int(labeled.sum()),
        "positive_rows": int((frame["deterioration_label"] == 1).sum()),
        "distinct_episodes": int(frame["deterioration_episode_start"].sum()),
        "affected_companies": int(frame.loc[frame["deterioration_episode_start"], "cik"].nunique()),
        "row_prevalence": float(
            (frame["deterioration_label"] == 1).sum() / max(int(labeled.sum()), 1)
        ),
    }


def build_and_audit_label(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    root = repository_root()
    config = read_yaml(root / "configs" / "label.yml")["label"]
    definition = config["definition"]
    labeled = deterioration_diagnostics(
        panel,
        horizon=int(config["horizon_fiscal_quarters"]),
        absolute_threshold=float(definition["future_minimum_below"]),
        relative_decline=float(definition["relative_decline_at_least"]),
        cooldown_quarters=int(config["episode_policy"]["episode_cooldown_quarters"]),
    )
    development_end = pd.Timestamp(config["audit_result"]["development_period_end"])
    holdout_start = pd.Timestamp(config["audit_result"]["final_holdout_start"])
    development = labeled.loc[labeled["decision_at"] <= development_end]
    holdout = labeled.loc[labeled["decision_at"] >= holdout_start]

    sensitivity_rows: list[dict[str, Any]] = []
    for absolute_threshold in [1.0, 1.5, 2.0]:
        for relative_decline in [0.30, 0.40, 0.50]:
            alternative = deterioration_diagnostics(
                development,
                horizon=int(config["horizon_fiscal_quarters"]),
                absolute_threshold=absolute_threshold,
                relative_decline=relative_decline,
                cooldown_quarters=int(config["episode_policy"]["episode_cooldown_quarters"]),
            )
            sensitivity_rows.append(
                {
                    "absolute_threshold": absolute_threshold,
                    "relative_decline": relative_decline,
                    **_episode_counts(alternative),
                }
            )
    sensitivity = pd.DataFrame(sensitivity_rows)

    slice_rows: list[dict[str, Any]] = []
    labeled["decision_year"] = labeled["decision_at"].dt.year
    for (period, sector), group in pd.concat(
        [
            development.assign(audit_period="development"),
            holdout.assign(audit_period="final_holdout"),
        ]
    ).groupby(["audit_period", "sector"]):
        slice_rows.append({"audit_period": period, "sector": sector, **_episode_counts(group)})
    by_year = (
        labeled.groupby(["decision_year", "sector"], as_index=False)
        .agg(
            labeled_rows=("deterioration_label", "count"),
            positive_rows=("deterioration_label", lambda values: int((values == 1).sum())),
            distinct_episodes=("deterioration_episode_start", "sum"),
            affected_companies=(
                "cik",
                lambda values: int(
                    labeled.loc[
                        values.index[labeled.loc[values.index, "deterioration_episode_start"]],
                        "cik",
                    ].nunique()
                ),
            ),
        )
        .sort_values(["decision_year", "sector"])
    )
    edge_cases = {
        "negative_operating_income_rows": int(labeled["negative_operating_income"].sum()),
        "invalid_interest_denominator_rows": int(labeled["interest_denominator_invalid"].sum()),
        "already_below_threshold_labeled_rows": int(
            (
                labeled["already_below_coverage_threshold"] & labeled["deterioration_label"].notna()
            ).sum()
        ),
        "missing_future_window_rows": int(labeled["deterioration_label"].isna().sum()),
    }
    holdout_sector = {
        str(cast(Any, row).sector): int(cast(Any, row).distinct_episodes)
        for row in pd.DataFrame(slice_rows)
        .query("audit_period == 'final_holdout'")
        .itertuples(index=False)
    }
    minimum = int(config["audit_result"]["minimum_holdout_episodes_per_sector"])
    if any(count < minimum for count in holdout_sector.values()):
        raise ValueError(
            f"Frozen holdout lacks the required {minimum} episodes per sector: {holdout_sector}"
        )
    processed = root / "data" / "processed"
    reports = root / "reports" / "generated"
    labeled.to_parquet(processed / "labeled_company_quarters.parquet", index=False)
    sensitivity.to_csv(reports / "label_threshold_sensitivity.csv", index=False)
    pd.DataFrame(slice_rows).to_csv(reports / "label_audit_by_period_sector.csv", index=False)
    by_year.to_csv(reports / "label_audit_by_year_sector.csv", index=False)
    evidence = {
        "status": "complete",
        "label_version": str(config["version"]),
        "definition": definition,
        "development": _episode_counts(development),
        "final_holdout": _episode_counts(holdout),
        "holdout_sector_episodes": holdout_sector,
        "edge_cases": edge_cases,
        "threshold_grid_size": len(sensitivity),
        "thresholds_frozen_before_modeling": True,
    }
    return labeled, evidence
