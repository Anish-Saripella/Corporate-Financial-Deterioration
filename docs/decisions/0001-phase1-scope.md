# ADR 0001: Phase 1 scope

**Status:** Accepted
**Date:** 2026-08-02

## Decision

Study currently listed Consumer Discretionary and Utilities issuers using free SEC and
FRED/ALFRED data. Forecast interest coverage, free-cash-flow margin, and total-debt-to-assets,
then predict four-quarter debt-service deterioration with logistic regression and gradient
boosting under time-aware validation.

## Consequences

The cyclical/defensive contrast supports financial interpretation. Excluding delisted issuers and
market data simplifies reproducibility but narrows external validity. HMMs, portfolios, scenario
engines, complex ensembles, and text models remain outside Phase 1.
