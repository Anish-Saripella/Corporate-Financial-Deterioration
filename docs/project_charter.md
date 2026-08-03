# Phase 1 Project Charter

## Decision problem

At each public-company filing date, identify companies in the fixed research universe that are
likely to experience material deterioration in debt-service capacity during the next four fiscal
quarters. The system supports analyst prioritization; it does not predict bankruptcy or claim
certainty about rare catastrophic events.

## Confirmed scope

- Consumer Discretionary as the cyclical sector.
- Utilities as the comparatively defensive, capital-intensive sector.
- Approximately 30 currently listed US companies per sector.
- Historical research window of 2012–2025, subject to the eligibility and event audits.
- Free public SEC EDGAR and FRED/ALFRED data only.
- Three forecast KPIs: interest coverage, free-cash-flow margin, total-debt-to-assets.
- Random walk and random walk with drift as forecasting baselines.
- Structural/regression state-space models as forecasting challengers.
- Regularized logistic regression and gradient-boosted trees as deterioration models.
- Expanding-window validation and an event-audited final holdout.
- Tableau dashboard using out-of-fold or genuine forward predictions.

## Non-goals for Phase 1

- Bankruptcy, default, LGD, EAD, expected loss, or regulatory capital estimation.
- Delisted-company population reconstruction.
- Daily monitoring or live trading signals.
- Market-price features without a stable, reusable public source.
- HMM regimes, complex stacking, RAG, deep learning, or company-specific forecasting systems.
- Causal claims about macroeconomic variables.

## Definition of done

Phase 1 is complete only when another person can recreate the research universe and analytical
table from public sources, reproduce the time-aware validation, generate the three KPI forecasts
and two classifier comparisons, run all quality checks, and regenerate documented Tableau-ready
outputs without using uncommitted business logic.
