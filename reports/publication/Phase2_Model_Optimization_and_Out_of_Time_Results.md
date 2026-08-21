# Phase 2 Model Optimization and Out-of-Time Results

## Executive result

The Phase 2 model-optimization work improved the corporate deterioration model without adding
companies, sectors, synthetic data, or proprietary information. The frozen ensemble achieved
**0.841 ROC-AUC** and **0.494
PR-AUC** on a sealed late-2024 out-of-time test whose four-quarter outcomes matured during 2025.
The preregistered ROC-AUC target was 0.80.

This is a screening model for analyst review. It does not assign credit ratings, predict bankruptcy,
or automate lending and investment decisions.

## What changed

Five model families and multiple ensemble methods were compared through nested,
quarterly rolling validation. The experiments included regularized logistic regression, random
forest, histogram gradient boosting, XGBoost, and an RBF support-vector challenger. Broad averaging
and hard window-by-window model switching did not improve performance consistently.

The selected model combines:

- 60% pooled XGBoost, which learns relationships shared across both sectors.
- 40% sector-specific XGBoost, which allows Consumer Discretionary and Utility relationships to
  differ.

Only labels available before each prediction origin were used. Feature screening, preprocessing,
and model tuning were repeated inside the training folds. The late-2024 test was not used to choose
features, models, blend weights, or thresholds.

## Results

| Metric | Optimization development | Sealed late-2024 test |
|---|---:|---:|
| ROC-AUC | 0.760 | **0.841** |
| PR-AUC | 0.462 | **0.494** |
| Recall | 80.5% | **85.7%** |
| Precision | 33.4% | 26.4% |
| Alert rate | 51.3% | 51.1% |
| Brier score | — | 0.106 |

The test contains 178 observations from 93 companies, including 28 deterioration events. The event
rate was 15.7%. Company-clustered 95% intervals are 0.742-0.924 for ROC-AUC and 0.317-0.691 for
PR-AUC.

At the common 80%-recall development policy, the alert rate declined from Phase 2's 57.6% to 51.3%
while PR-AUC increased from 0.412 to 0.462. This is the most comparable workload comparison because
both numbers are development out-of-fold estimates on the Phase 2 population. On the sealed test,
the frozen policy alerted on 51.1% of observations and found 85.7% of deteriorations. This is a
meaningful workload reduction, although reviewing roughly half of observations remains substantial.

## Sector results

| Sector | Events | ROC-AUC | PR-AUC | Recall | Alert rate |
|---|---:|---:|---:|---:|---:|
| Consumer Discretionary | 21 | 0.801 | 0.492 | 90.5% | 65.4% |
| Utilities | 7 | 0.872 | 0.625 | 71.4% | 31.1% |

The frozen thresholds produced lower Utility recall than the 80% development target. They were not
retuned after observing the test. The Utility estimate is also based on only seven events and should
not be treated as a stable population estimate.

## Outcome

The Phase 2 optimization achieved its principal goal: ROC-AUC exceeded 0.80 on genuinely unseen
time-period evidence. PR-AUC and workload also improved in the comparable development analysis,
and the sealed test supported those gains in a later period. The result demonstrates stronger
ranking performance, model comparison, leakage-aware ensemble construction, and disciplined
out-of-time evaluation.

The next useful evidence is another matured future period. Additional tuning against this test would
weaken rather than strengthen the project.

The [combined Phase 1 + Phase 2 research report](Corporate_Financial_Deterioration_Combined_Phase1_Phase2_Research_Report.pdf)
provides the full business, financial, methodological, and limitations context. Exact published
metrics are available in the [machine-readable evidence file](../source_data/phase3_final_metrics.json).
