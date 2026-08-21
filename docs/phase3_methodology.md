# Phase 3 model accuracy and ensemble methodology

## Purpose

Phase 3 improves model discrimination and analyst workload without changing the frozen 117-company
population or four-quarter deterioration definition. ROC-AUC is the lead discrimination metric;
PR-AUC remains a required guardrail because deterioration events are less common than non-events.

## Validation design

Development uses quarterly rolling origins and four-quarter validation windows. At every origin,
training includes only decisions before the embargo boundary and labels whose `label_available_at`
date precedes the origin. Preprocessing, feature screening, and hyperparameter selection are fitted
inside the training fold. When overlapping validation windows produce more than one prediction for
a decision, the primary comparison uses the model trained closest to, but not after, that decision.

Decisions from 1 July through 31 December 2024 form the sealed test. Their four-quarter outcomes
mature during 2025. The test was opened only after the feature process, model blend, thresholds, and
configuration hash were frozen.

## Models and ensembles

The comparison includes pooled and sector-specific versions of regularized logistic regression,
random forest, Extra Trees, histogram gradient boosting, XGBoost, and an RBF support-vector
challenger. Static averages, rank averaging, inner-window winner selection, performance weighting,
stacking, and time-adaptive weights are evaluated from cross-fitted probabilities.

Adaptive weights may use only earlier validation windows that are fully completed before the
current origin. This prevents the model from choosing a winner using the outcome of the window it
is predicting. Hard switching performed poorly and was not selected.

The frozen champion blends 60% pooled XGBoost and 40% sector-specific XGBoost. The pooled component
uses information shared by both sectors; the sector-specific component allows Consumer
Discretionary and Utility relationships to differ.

## Decision policy

Development thresholds are sector-specific. Within each sector, the selected threshold is the
highest probability cutoff that reaches at least 80% development recall, which minimizes review
volume subject to that requirement. Thresholds are not changed after the sealed test is opened.

## Results and interpretation

The champion achieved 0.760 development ROC-AUC and 0.462 development PR-AUC. At the frozen
development thresholds, recall was 80.5%, alert rate was 51.3%, and precision was 33.4%.
Compared with Phase 2's development policy at the same recall target, PR-AUC increased from 0.412
and the alert rate declined from 57.6%. The workload improvement is useful but incomplete: the
model still sends about half of company-quarter observations to analysts.

On the sealed late-2024 test, ROC-AUC was 0.841 and PR-AUC was 0.494 across 178 observations, 93
companies, and 28 events. Overall recall was 85.7%. Company-clustered 95% bootstrap intervals were
0.742-0.924 for ROC-AUC and 0.317-0.691 for PR-AUC.

The result meets the preregistered 0.80 ROC-AUC target, but the confidence intervals are wide.
Utility recall was 71.4% across only seven events, while Consumer Discretionary recall was 90.5%.
The evidence therefore supports a successful out-of-time test, not a claim that every future period
or sector will achieve 0.80+ ROC-AUC.

## Reproduction

```bash
python -m cfd.cli run-phase3-development
python -m cfd.cli evaluate-phase3-final-test   # one-time sealed evaluation
python -m cfd.cli build-phase3-evidence
```

The final-test command refuses to run twice and refuses to run if the frozen configuration hash has
changed.
