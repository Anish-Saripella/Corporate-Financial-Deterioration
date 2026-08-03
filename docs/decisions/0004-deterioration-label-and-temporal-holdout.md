# ADR 0004 — Deterioration Label and Temporal Holdout

**Status:** Accepted
**Date:** 2026-08-02
**Applies from:** Stage 9

## Decision

Debt-service deterioration is positive when, within the next four fiscal quarters, interest
coverage both falls below 1.5 and declines at least 40% from the current value. Consecutive
positive rows are collapsed into episodes with a four-quarter cooldown. The thresholds were
selected from a nine-combination, economically plausible grid using development-period event
counts—not model performance.

The development period ends 2022-12-31. The final holdout begins 2023-01-01 and remains locked
during preprocessing, feature selection, forecasting, classification, calibration, and model
selection. Training rows whose outcomes would not have been known at a validation origin are
embargoed.

## Evidence

The development sample contains 2,191 labeled rows, 471 positive rows, 164 distinct episodes, and
43 affected companies. The holdout contains 457 labeled rows, 96 positive rows, and 29 episodes:
17 in Consumer Discretionary and 12 in Utilities. These counts support sector reporting while
preserving a meaningful out-of-time period.

## Consequences

The target represents measurable deterioration in debt-service capacity, not bankruptcy or
default. PR-AUC is the primary classification metric because positives are a minority; calibration,
recall, lift, false-alert rate, stability, and interpretability remain required decision criteria.
