"""Stage 27: write an accessible Phase 2 development research report."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from cfd.config import repository_root


def _metric_line(row: pd.Series) -> str:
    return (
        f"PR-AUC {row['PR_AUC']:.3f}, precision {row['precision']:.3f}, "
        f"recall {row['recall']:.3f}, and Brier score {row['Brier_score']:.3f}"
    )


def run_stage_27() -> dict[str, Any]:
    """Summarize real development evidence without overstating final validity."""

    root = repository_root()
    reports = root / "reports" / "generated"
    metrics = pd.read_csv(reports / "phase2_metrics.csv")
    overall = metrics.loc[metrics["slice"] == "Overall"].sort_values("PR_AUC", ascending=False)
    best = overall.iloc[0]
    primary = overall.loc[overall["model"].str.startswith("partially_pooled_logistic")].iloc[0]
    forecast = pd.read_csv(reports / "phase2_forecast_metrics.csv")
    monitoring = pd.read_csv(reports / "phase2_feature_monitoring.csv")
    policy = pd.read_csv(reports / "phase2_development_policy_selection.csv").iloc[0]
    readiness = json.loads((reports / "phase2_readiness.json").read_text(encoding="utf-8"))
    governance = json.loads((reports / "stage26_summary.json").read_text(encoding="utf-8"))
    universe = pd.read_parquet(root / "data" / "processed" / "phase2_selected_universe.parquet")
    sector_counts = universe.groupby("sector")["cik"].nunique().to_dict()
    warnings = monitoring.loc[monitoring["severity"] != "normal", "feature"].tolist()
    report = f"""# Phase 2 Development Research Report

## Executive conclusion

Phase 2 studies {len(universe)} currently active issuers—
{sector_counts["Consumer Discretionary"]} Consumer Discretionary and
{sector_counts["Utilities"]} Utilities—and implements a reproducible real-data analytical
pipeline. The strongest development
ranking is `{best["model"]}`, with {_metric_line(best)}. This is encouraging relative to the Phase 1
development benchmark, but it is **not a final performance result** because the 2023-and-later
period was already examined in Phase 1.

The project is currently `{readiness["status"]}` for a final Phase 2 claim. The panel contains
{readiness["sector_evidence"][0]["episodes"]} Consumer Discretionary and
{readiness["sector_evidence"][1]["episodes"]} Utility deterioration episodes, below the registered
150-per-sector evidence gate, and no new untouched test boundary has matured.

## Population and sampling

Companies are first mapped to a sector using the controlled SEC SIC table. SIC is the SEC's primary
four-digit industry code. A mapped issuer must be an active US operating company on August 2, 2026,
listed on NYSE, NASDAQ, or NYSE American, and have usable 10-K/10-Q history through December 31,
2025. Delisted firms remain excluded, so the conclusions apply to survivors rather than the full
historical corporate-credit population.

Eligible issuers receive a deterministic pseudo-random score from seed 20260802 and their CIK. The
algorithm samples without replacement across industry and three filing-based asset-size tiers.
Eligibility requires reliable interest-coverage history, while optional predictors are assessed at
the company-quarter level. Occasional historical gaps are permitted. The unequal sector sizes are
preserved in evaluation, while each sector receives equal total weight during model fitting.

## Outcome and financial meaning

The benchmark label asks whether interest coverage—operating income divided by positive interest
expense—falls below 1.5 times and declines by at least 40% during the next four quarters. It is an
early-warning definition of weaker debt-service capacity, not bankruptcy. Registered sensitivity
labels vary the horizon and coverage threshold and add a two-of-three rule using negative free cash
flow and rising leverage. They are defined before inspecting model performance.

## Models and validation

Nested expanding-window validation respects time: earlier quarters train the model and later
quarters validate it. Hyperparameters and feature selection occur inside each training window. The
partially pooled logistic model is primary, pooled logistic is the benchmark, and constrained
gradient boosting is the nonlinear challenger. Missing values are imputed inside each fold,
preventing future information from entering training.

The registered partially pooled primary model achieved {_metric_line(primary)}. The nonlinear
challenger achieved {_metric_line(best)} over {int(best["observations"])} unique out-of-fold
company-quarters. PR-AUC emphasizes ranking of the relatively uncommon deterioration events. The
Brier score is the mean squared probability error, so lower is better. Precision measures the share
of alerts that are events; recall measures the share of events found.

Forecasts are evaluated separately by KPI and are not primary classifier inputs. Forecast
backtests cover {len(forecast):,} KPI/model/sector/horizon summaries and use empirical residual
intervals instead of assuming normally distributed errors.

## Interpretation and monitoring

The pipeline produces {governance["explanations"]} company-quarter explanation records. Reason
codes identify unusually
weak coverage, cash flow, leverage, peer position, financing conditions, forecast uncertainty, or
filing delay. These are predictive associations and are explicitly non-causal.

Monitoring compares pre-2023 development distributions with 2023-2025. The current run flags
{len(warnings)} of seven monitored features: {", ".join(warnings) if warnings else "none"}. PSI is
a practical drift diagnostic: 0.10 requests investigation and 0.25 escalation. A flag does not by
itself authorize retraining.

## Calibration and alert policy

The best development calibration choice for the registered primary specification is
`{policy["calibration_method"]}` with `{policy["calibration_scope"]}` scope. Calibration selection
is based only on earlier out-of-fold predictions and later development rows. Sector-specific
calibration could not be estimated reliably because the
earlier calibration fold did not contain both outcome classes in every sector.

The screening policy targets 80% recall within each sector. The Consumer threshold is
{policy["consumer_threshold"]:.3f} and the Utility threshold is {policy["utility_threshold"]:.3f}.
Together they produce {policy["alert_rate"]:.1%} workload and {policy["precision"]:.1%} precision.
Precision is reported as the operational cost of prioritizing recall; thresholds are not forced to
match across sectors.

## Limitations and next evidence

- Active-company-only selection creates survivorship bias.
- The number of issuers remains modest, and quarterly rows from one company are correlated.
- The former strict company-level certification remains a quality slice and is not an exclusion.
- Development model selection is optimistic relative to a genuinely untouched test.
- Final acceptance requires future four-quarter labels, one-time evaluation, and prospective
  shadow scoring under the frozen alert policy.
"""
    destination = reports / "phase2_development_research_report.md"
    destination.write_text(report, encoding="utf-8")
    result = {
        "status": "complete",
        "report": str(destination),
        "leading_model": str(best["model"]),
        "leading_pr_auc": float(best["PR_AUC"]),
        "final_test_evaluated": False,
        "synthetic_data_used": False,
    }
    (reports / "stage27_summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result
