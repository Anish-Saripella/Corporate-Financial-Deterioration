# Corporate Financial Deterioration Early-Warning Platform

A reproducible, point-in-time data science project that forecasts corporate financial KPIs
and predicts deterioration in debt-service capacity for a fixed research universe of currently
listed US Consumer Discretionary and Utilities companies.

## Phase 1 scope

- 60 companies: approximately 30 per sector after documented eligibility screening.
- Free public data from SEC EDGAR and FRED/ALFRED only.
- Filing-aware quarterly fundamentals standardized to fiscal quarters without discarding dates.
- Forecast interest coverage, free-cash-flow margin, and total-debt-to-assets.
- Compare random-walk baselines with structural and regression state-space models.
- Compare regularized logistic regression with gradient-boosted trees.
- Use expanding-window validation and a final out-of-time holdout.
- Publish a documented financial-research report with reproducible evidence charts.

The target is financial deterioration, not bankruptcy or default. The fixed current-company
universe intentionally simplifies data collection and introduces survivorship bias; the project
does not claim population-level default-model validity.

## Quick start

Requirements: Python 3.12, Git, `make`, and an internet connection for initial installation and
source-data ingestion.

```bash
cp .env.example .env
# Set SEC_USER_AGENT and FRED_API_KEY in .env
make bootstrap
make check
make dagster
```

`make bootstrap` installs `uv` inside `.venv`, creates a locked environment, and installs the
development tools. It does not modify system Python.

## Reproduce the completed Phase 1 product

```bash
make reproduce-phase1
```

Network ingestion is deliberately separate from local validation. Add real credentials to
`.env`, never commit that file, and follow the source-specific usage policies in
[`docs/data_sources.md`](docs/data_sources.md).

## Repository map

- `configs/`: versioned scope, concepts, label, universe, and macro-series decisions.
- `src/cfd/`: reusable ingestion, transformation, feature, forecasting, and modeling code.
- `sql/`: versioned DuckDB transformations.
- `tests/`: unit, data-contract, integration, and later leakage tests.
- `notebooks/`: numbered analysis notebooks; production logic belongs in `src/cfd/`.
- `docs/`: charter, point-in-time policy, decisions, validation plan, and data dictionaries.
- `data/`: ignored raw/intermediate/processed data with committed directory placeholders.
- `dashboards/powerbi/`: optional Power BI prototype and validation evidence retained for reference.
- `reports/publication/`: publication-style Phase 1 research report in Word and PDF.

## Reproducibility policy

Generated data and model artifacts are not committed. Each acquisition writes a manifest with
source URL, parameters, retrieval timestamp, checksum, and software version. Configurations,
schemas, transformations, tests, and small fixtures are committed. See
[`docs/reproducibility.md`](docs/reproducibility.md).

## What has been completed

The full chronological execution plan and completion gates are documented in
[`docs/phase1_implementation_plan.md`](docs/phase1_implementation_plan.md).
The accepted point-in-time, KPI-definition, company-certification, and replacement assumptions are
recorded in
[`docs/decisions/0003-point-in-time-panel-and-modeling-eligibility.md`](docs/decisions/0003-point-in-time-panel-and-modeling-eligibility.md).

The core Phase 1 analytical study is complete. The work completed so far is:

1. **Research scope and financial question** — defined a forward-looking deterioration target
   focused on weakening debt-service capacity rather than bankruptcy or default.
2. **Company universe** — certified 60 currently listed companies: 30 Consumer Discretionary and
   30 Utilities. Fourteen initial selections were replaced after coverage, continuity, lineage, or
   denominator checks failed.
3. **Point-in-time data pipeline** — collected and normalized public SEC EDGAR fundamentals and
   FRED/ALFRED economic data while retaining filing and availability dates to prevent future-data
   leakage.
4. **Financial measures** — standardized interest coverage, free-cash-flow margin, and
   debt-to-assets across company fiscal calendars.
5. **Deterioration outcome** — froze a four-quarter warning definition requiring interest coverage
   below 1.5x and a decline of at least 40% from the current level.
6. **Exploratory analysis** — produced audited distributions, sector comparisons, time trends,
   coverage diagnostics, event counts, and peer-relative financial analysis.
7. **Financial forecasting** — compared random walk, drift, local-level, local-trend, and dynamic
   regression approaches at one- and four-quarter horizons.
8. **Classification experiments** — compared regularized logistic regression and constrained
   gradient-boosted trees across planned feature groups.
9. **Temporal validation** — used three expanding training windows, out-of-sample development
   predictions, and an untouched 2023-and-later holdout.
10. **Final model evaluation** — the selected gradient-boosted model achieved 0.397 holdout
    PR-AUC, 0.563 recall, 0.333 precision, 1.97x top-decile lift, and 0.159 Brier score across 457
    observations. Consumer Discretionary results were stronger than Utilities.
11. **Reproducible analytical product** — implemented versioned configuration, DuckDB/Parquet
    storage, manifests, automated tests, model documentation, and a production asset graph.
12. **Publication report** — completed a financial-research report covering the question, data,
    methods, results, interpretation, limitations, and evidence charts. The report intentionally
    excludes project-management and future-roadmap content so it reads as a focused study.
13. **Optional Power BI prototype / Stage 17 experiment** — created a PBIX, certified import
    workbook, four report-page concepts, screenshots, and validation notes. Power BI is retained as
    optional evidence of business-intelligence experience, but it is not required for the core
    research project to be considered complete.
14. **Release documentation** — recorded assumptions, limitations, lineage, model governance,
    reproduction commands, and the Power BI experiment under the stage execution documents.

Detailed evidence is available in
[`docs/stages_0_7_execution.md`](docs/stages_0_7_execution.md),
[`docs/stages_8_12_execution.md`](docs/stages_8_12_execution.md),
[`docs/stages_13_16_execution.md`](docs/stages_13_16_execution.md),
[`docs/stages_17_18_execution.md`](docs/stages_17_18_execution.md), and
[`docs/model_card.md`](docs/model_card.md). The publication report is available at
[`reports/publication/Corporate_Financial_Deterioration_Phase1_Research_Report.pdf`](reports/publication/Corporate_Financial_Deterioration_Phase1_Research_Report.pdf).
Run `.venv/bin/cfd verify-source-manifests` to recheck every cached acquisition against its
recorded checksum.
After freezing or deliberately refreshing the universe, run `.venv/bin/cfd materialize-final-store`
to retain company financial data locally for only the selected 60. Downstream modeling uses this
local Parquet/DuckDB store and makes no SEC API calls.
Reproduce Stages 8–12 from the certified local store with:

```bash
.venv/bin/cfd run-stages-8-12
```

Reproduce the completed modeling pipeline with:

```bash
.venv/bin/cfd run-stages-13-16
```

## Phase 2 plan and next steps

Phase 2 should improve the model before expanding presentation features. Every change must be
tested on future time periods that were not used to fit or tune the model.

### 1. Improve the training sample

- Add delisted and financially distressed companies to reduce survivorship bias.
- Expand beyond Consumer Discretionary and Utilities while retaining sector-level reporting.
- Increase the number of deterioration events so performance estimates are less sensitive to a
  small number of companies or quarters.
- Review alternative deterioration definitions and horizons through planned sensitivity tests;
  do not choose the definition that merely produces the best result after the fact.

### 2. Improve financial and economic features

- Add debt maturity pressure, short-term debt share, liquidity reserves, profitability trend,
  working-capital stress, capital-expenditure burden, and interest-expense growth where public data
  quality supports them.
- Add changes and trends—not only current levels—for coverage, margins, leverage, liquidity, and
  operating performance.
- Test more useful sector-relative measures because the normal range of a financial ratio differs
  across industries.
- Improve macroeconomic features with interest-rate changes, credit spreads, inflation, recession
  indicators, and sector-sensitive economic variables using historically available values.
- Measure missingness and reporting delays directly; late or incomplete reporting may itself carry
  information, but it must be modeled without using future knowledge.

### 3. Improve time-series forecasts

- Compare the current structural models with seasonal baselines, autoregressive models, and pooled
  panel forecasts that can learn from related companies.
- Tune models separately by KPI and forecast horizon instead of assuming one method is best for
  every target.
- Improve four-quarter forecast ranges because several Phase 1 intervals were too narrow.
- Test conformal prediction or other empirically calibrated intervals and require observed coverage
  to remain close to the stated confidence level across sectors and time periods.
- Evaluate whether forecast features truly improve the deterioration classifier beyond current
  financial ratios; remove them if they add complexity without reliable out-of-sample value.

### 4. Improve classification performance

- Tune logistic regression and gradient-boosted trees using nested, time-ordered validation so
  model choices cannot learn from the final evaluation period.
- Test class weighting and carefully controlled sampling approaches to improve event detection
  without creating unrealistic event rates.
- Optimize model settings for PR-AUC, recall, precision, calibration, and ranking lift together
  rather than maximizing one metric.
- Evaluate survival analysis for time-to-deterioration and panel models that account for repeated
  observations from the same company.
- Consider sequence models only after the expanded dataset is large enough to support them and only
  if they outperform simpler baselines consistently across time and sectors.
- Use repeated temporal backtests or bootstrap methods at the company level to add uncertainty
  ranges around performance differences.

### 5. Improve sector performance and probability reliability

- Investigate why Utilities had weaker PR-AUC and precision than Consumer Discretionary.
- Test sector-specific models, shared models with sector interactions, and sector-specific
  probability recalibration.
- Compare Platt scaling and isotonic calibration using training-period data only.
- Require reliability charts and calibration error by sector, time period, and risk band before
  interpreting the probability as an absolute risk estimate.

### 6. Improve alert thresholds and analyst usefulness

- Choose alert thresholds using explicit costs for missed deterioration events and unnecessary
  analyst reviews.
- Report results at several possible review capacities—for example, the top 5%, 10%, and 20% of
  companies—rather than relying on one threshold.
- Add decision-curve or expected-value analysis to show whether model-guided review improves on
  reviewing every company or selecting companies at random.
- Conduct prospective shadow scoring: produce scores on schedule, do not act on them initially,
  and compare predictions with outcomes as they become observable.

### 7. Improve interpretation and monitoring

- Provide company-level explanations that connect each alert to the source financial ratios,
  recent changes, peer position, forecast direction, and uncertainty.
- Distinguish predictive importance from causal explanation in every output.
- Monitor changes in company mix, feature distributions, event rates, calibration, and model
  performance over time.
- Define retraining and review triggers before live monitoring begins.

### Phase 2 acceptance criteria

Phase 2 should be accepted only if it demonstrates:

- stronger and more stable PR-AUC than the Phase 1 model across multiple future periods;
- improved precision without an unacceptable reduction in recall, or a clearly justified trade-off;
- probability calibration that remains reliable across sectors and time periods;
- forecast intervals with observed coverage close to their stated level;
- reduced Consumer Discretionary–Utilities performance gaps;
- uncertainty ranges showing that improvements are unlikely to be random sample variation; and
- a documented analyst-review benefit under realistic workload assumptions.

Power BI work is optional. If an interactive interface is revisited, prefer a code-native dashboard
that can be versioned and tested with the Python pipeline unless Power BI is specifically required
for a target role or audience.
