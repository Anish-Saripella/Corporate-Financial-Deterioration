# Stages 8–12 Execution Record

**Execution date:** 2026-08-02
**Universe:** `selected-universe-v2-certified`
**Financial cutoff:** 2025-12-31

## Outcome

Stages 8–12 execute with one command and use only the certified local Parquet/DuckDB store:

```bash
.venv/bin/cfd run-stages-8-12
```

The run certified 60 companies and 3,150 company-quarter decision rows. All 780 certification
rules passed; duplicate keys, future financial facts, and future macro vintages each had zero
violations. Fourteen companies were replaced before labels or models were consulted: four from
the frozen reserve list and ten from the deterministic expanded candidate order. The retained
local financial store contains only the final 60 companies.

| Sector | Removed | Replacement | Replacement source |
|---|---:|---:|---|
| Consumer Discretionary | MOD | SGI | Frozen reserve |
| Consumer Discretionary | CNK | AAP | Expanded candidate order |
| Consumer Discretionary | TNL | WWW | Frozen reserve |
| Consumer Discretionary | XHR | ANF | Expanded candidate order |
| Consumer Discretionary | PRSU | OXM | Frozen reserve |
| Consumer Discretionary | BBY | SRI | Expanded candidate order |
| Consumer Discretionary | RH | UAA | Expanded candidate order |
| Utilities | PPL | FE | Frozen reserve |
| Utilities | AVA | PCG | Expanded candidate order |
| Utilities | WTRG | ES | Expanded candidate order |
| Utilities | NJR | CWT | Expanded candidate order |
| Utilities | DTE | UTL | Expanded candidate order |
| Utilities | OGE | NWN | Expanded candidate order |
| Utilities | NFG | BKH | Expanded candidate order |

Each removal failed one or more observations, continuity, or coverage requirements for at least
one required KPI. Exact rule-level evidence remains in the generated certification and replacement
audit tables; this table is the stable public decision record.

## Recorded assumptions and scope choices

1. The research universe uses currently listed US companies and therefore has survivorship bias.
2. Fiscal quarters are standardized as issuer-relative FQ1–FQ4, while joins retain actual period
   ends and filing dates.
3. SEC facts are selected deterministically from the filing data available at each decision;
   amendment effects are not a separate research question.
4. ALFRED series use recorded vintages. Non-vintage FRED series use observation date plus one day
   as a transparent availability proxy.
5. Interest coverage, free-cash-flow margin, and debt-to-assets use one economic definition across
   sectors. Total debt prefers a directly reported concept and otherwise uses short- plus long-term
   debt.
6. Negative operating income is valid. Invalid denominators create missing values and flags.
7. A company must have at least 24 observed quarters, 16 consecutive quarters, and 80% coverage
   for every KPI. The TTM warm-up does not enter the coverage denominator.
8. A failure of any strict KPI or lineage rule replaces the whole company; standards are not
   relaxed and KPI-specific samples are not used.
9. Raw values are retained. Imputation, clipping, scaling, encoding, and feature selection are fit
   independently inside each training fold.
10. The pooled cross-sector deterioration model remains the Phase 1 modeling design; sector and
    regime results will be reported as diagnostic slices before sector-specific challengers are
    justified.

## Stage 9 — frozen label

The label identifies a four-quarter decline in debt-service capacity: future minimum interest
coverage below 1.5 **and** a relative decline of at least 40%. The development sample has 164
distinct episodes and 21.5% row prevalence. The locked 2023+ holdout has 29 episodes and 21.0%
row prevalence. Thresholds are frozen as `1.0.0-frozen`; the target is not bankruptcy.

## Stage 10 — exploratory analysis

Eight figures use `publication-theme-v1`, a consistent orange/blue sector palette, uniform
`Corporate Financial Deterioration | …` titles, restrained annotation, and identical export rules.
Every figure is stored under `reports/figures/stage10/` as a 300-DPI PNG and editable SVG. The
machine-readable figure index is `figure_manifest.json`.

The EDA confirms economically meaningful sector contrast. Median interest coverage is about 5.25
for Consumer Discretionary and 1.81 for Utilities; median debt-to-assets is about 0.22 and 0.34,
respectively. Lag-one dependence and signal-to-noise diagnostics support forecasting all three
KPIs, with particularly persistent leverage in Consumer Discretionary and interest coverage in
Utilities. These diagnostics motivate baseline and state-space comparisons; they do not select a
winner in advance.

## Stage 11 — feature contract

The feature table has 3,150 rows, 26 registered numeric features, and two categorical features.
It includes current KPI levels, year-over-year changes, four-quarter trends and volatility,
sector-relative ranks, macro variables, and limited economic interactions. Future label
diagnostics are excluded. The feature dictionary records availability and fold-fitted processing.

## Stage 12 — temporal design

Three expanding-window folds validate on 2019-10-01–2020-09-30,
2020-10-01–2021-09-30, and 2021-10-01–2022-09-30. Each fold embargoes rows whose four-quarter
label window is unavailable at the validation origin. The final holdout begins 2023-01-01 and is
locked. PR-AUC is the primary classifier metric; calibration and sector/time stability remain
required selection evidence.

## Reproducibility evidence

- Configuration: `configs/analytical_panel.yml`, `configs/label.yml`,
  `configs/feature_registry.yml`, `configs/temporal_validation.yml`, and
  `configs/plot_style.yml`.
- Generated summaries: `reports/generated/stages_8_12_summary.json`, label audits, certification
  and replacement reports, feature dictionary, and temporal-fold summary.
- Processed contracts: certified panel, labels, model features, split assignments, and locked
  holdout in `data/processed/` and the corresponding DuckDB marts.
- Verification: `pytest`, Ruff, mypy, configuration validation, and source-manifest checksum
  validation.
