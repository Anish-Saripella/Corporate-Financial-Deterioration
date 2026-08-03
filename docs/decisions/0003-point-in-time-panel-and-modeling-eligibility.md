# ADR 0003 — Point-in-Time Panel and Modeling Eligibility

**Status:** Accepted
**Date:** 2026-08-02
**Applies from:** Stage 8

## Context

The selected universe was constructed using filing-history and broad accounting-data gates. Before
modeling, the analytical panel requires stricter rules that protect point-in-time validity,
consistent KPI interpretation, and company-level data quality. These rules must be fixed before
the deterioration label, event prevalence, or model performance can influence decisions.

## Decisions

1. Financial facts become usable only when filed. Original and amended accessions are retained;
   amended or restated values never enter a historical decision row before the amendment date.
2. Fiscal labels standardize issuer-relative FQ1–FQ4 positions, but macroeconomic observations are
   joined using actual period-end and historical release/vintage dates.
3. KPI definitions are consistent across companies:
   - interest coverage = operating income / positive interest expense;
   - free-cash-flow margin = (operating cash flow − capital expenditures) / revenue;
   - leverage = total debt / total assets, with short-term plus long-term debt used only when a
     directly reported total-debt concept is unavailable.
4. Negative operating income remains economically meaningful. Invalid or negligible denominators
   produce missing values and explicit flags rather than fabricated ratios.
5. Raw values and edge-case indicators are preserved. Any clipping or winsorization is fitted only
   on each temporal training fold and then applied unchanged to validation and test observations.
6. Every company must pass the same strict modeling-eligibility rules for all three KPIs: at least
   24 observed quarters, 16 consecutive quarters, 80% coverage, valid lineage, no unresolved
   essential mappings, and no point-in-time leakage or duplicate analytical keys.
   KPI coverage begins with that KPI's first valid observation, so the mechanically unavailable
   three-quarter TTM warm-up is not counted as missing; observation-count and continuity gates
   independently prevent short histories from passing.
7. KPI-specific exclusion is rejected for Phase 1. If any required KPI fails, the company is
   replaced using the next same-sector issuer in the frozen reserve order. The replacement must
   pass identical rules. Outcomes, event prevalence, and model performance cannot influence this
   decision.
8. If reserves are insufficient, work stops and the candidate pool is expanded transparently using
   the original rules and seed. Eligibility standards will not be weakened.
9. The 60-company universe remains frozen unless this pre-model data-quality audit identifies a
   material failure. Every replacement records the original company, replacement, sector, failed
   rule, evidence, timestamp, and resulting universe version.
10. Survivorship bias from using currently listed companies is accepted and must appear in public
    findings, the model card, and dashboard documentation.
11. Deterioration thresholds and the final holdout are finalized only after a development-period
    event audit, without optimizing against final model performance.

## Consequences

Stage 8 is a formal data-certification stage, not merely feature construction. Modeling cannot
start until all 60 final companies pass every configured gate and leakage tests. A reserve Company
Facts file may be downloaded only when a documented replacement audit requires it; if selected,
the local store is rematerialized so it again contains only the certified final 60.

These constraints reduce sample flexibility but make the resulting forecasts, risk classifications,
and public claims more interpretable and defensible.

## Mapping clarification recorded during Stage 8

The pre-model audit may add a standard US-GAAP tag only when its definition is economically
equivalent to the configured concept across issuers. Examples include payments for capital
improvements or construction in process as capital expenditures, and net non-operating interest
expense as an interest-cost fallback. Mapping additions are applied to every company and rerun
before any replacement decision. Company-specific custom concepts are not silently substituted.
