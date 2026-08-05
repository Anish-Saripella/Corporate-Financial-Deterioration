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

## Project progress record

This milestone log documents the transition from Phase 1 completion to Phase 2 planning. Commit
identifiers provide a permanent link between the stated milestone and the repository contents.

| Date | Milestone | Evidence |
|---|---|---|
| 2026-08-04 | Completed the reproducible Phase 1 analytical release and initial research report. | Commit `c5806ba` |
| 2026-08-05 | Expanded the Phase 1 report with sector KPI, time-series, seasonality, and financial interpretation. | Commit `3ed84ed` |
| 2026-08-05 | Completed the review cycle covering chart legibility, hypothesis conclusions, plain-language methodology, sector operating characteristics, and the distinction between model performance and sector risk. | Commits `6eafe95` through `f668142` |
| 2026-08-05 | Finalized and pushed the Phase 1 report in both PDF and Word formats with its reproducible generation script and supporting figures. | Final Phase 1 report commit `f668142` |
| 2026-08-05 | Formally closed Phase 1 and documented the Phase 2 model-improvement audit, workstreams, execution order, and acceptance criteria. | Commit `652e196` |

The committed Phase 1 publication files are:

- [`Corporate_Financial_Deterioration_Phase1_Research_Report.pdf`](reports/publication/Corporate_Financial_Deterioration_Phase1_Research_Report.pdf)
- [`Corporate_Financial_Deterioration_Phase1_Research_Report.docx`](reports/publication/Corporate_Financial_Deterioration_Phase1_Research_Report.docx)
- [`generate_publication_report.py`](scripts/generate_publication_report.py)

## Phase 2 audit and implementation plan

Phase 1 is closed. Its frozen benchmark is the pooled gradient-boosted model with 0.397 holdout
PR-AUC, 0.563 recall, 0.333 precision, 1.97x top-decile lift, and 0.159 Brier score. Phase 2 should
focus on stronger evidence and model performance before adding presentation features.

The 2023-and-later holdout has now been evaluated and discussed. It is no longer an untouched test
set and must not be reused to claim final Phase 2 performance. Phase 2 must reserve a new future
period or use a prospective evaluation window that remains inaccessible until the model and alert
policy are frozen.

### Phase 1 audit: what should be improved

| Audit finding | Why it matters | Phase 2 response |
|---|---|---|
| Only 60 currently listed issuers | The sample excludes delisted firms and contains only 30 independent companies per sector, even though it has many quarterly rows. This limits generalization and understates severe distress. | Add delisted, acquired, bankrupt, and financially distressed histories; expand the number of issuers before increasing model complexity. |
| Repeated and overlapping observations | Adjacent four-quarter labels share future quarters, so 3,150 rows are not 3,150 independent experiments. | Report company- and episode-level results; use issuer-clustered uncertainty estimates and embargoed temporal validation. |
| One researcher-defined outcome | The 1.5x/40% coverage rule is interpretable but does not capture every form of financial deterioration. | Pre-register sensitivity tests for alternative thresholds, horizons, cash-flow stress, covenant-like pressure, and time-to-event outcomes. Do not select a label merely because it improves model metrics. |
| Survivorship and sector scope | Results from two sectors of surviving public firms cannot represent the broader corporate-credit population. | Correct survivorship bias first, then add sectors in economically coherent groups with separate reporting. |
| Utility classification is weaker | Utility holdout PR-AUC was 0.332 and precision was 0.225, versus 0.468 and 0.439 for Consumer Discretionary. | Diagnose label suitability, feature coverage, rate-regulation effects, capital-spending cycles, and sector calibration before choosing a separate model. |
| Moderate overall alert precision | Approximately one in three Phase 1 alerts became an event under the study definition. | Add cost-sensitive threshold selection, review-capacity analysis, and features that distinguish temporary weakness from sustained deterioration. |
| Distribution shift | The holdout alert rate exceeded the development design range and performance varied by temporal fold. | Add rolling-origin backtests, regime features, drift monitoring, and a new untouched future test period. |
| Forecast intervals under-covered | Several four-quarter ranges were too narrow, making forecast uncertainty appear more reliable than it was. | Recalibrate intervals by KPI, sector, and horizon; test conformal or empirical residual intervals. |
| Forecast features gave mixed benefits | Forecasts helped the boosted model in some development tests but not every fold or the logistic model. | Run an ablation test against current and historical ratios; retain forecasts only if improvement is stable and worth the added complexity. |
| Probability quality varies by sector | A lower Brier score did not guarantee stronger ranking, and Utility calibration error remained material. | Evaluate discrimination and calibration separately; test sector-specific probability recalibration using training data only. |
| Limited model comparison | Phase 1 appropriately emphasized logistic regression and constrained gradient boosting, but did not exhaust panel or time-to-event approaches. | Add interpretable panel, discrete-time hazard, and survival challengers before considering complex sequence models. |
| No decision-cost validation | A statistical improvement may not improve an analyst's workload or financial decisions. | Define the cost of missed events and false alerts; compare top-5%, top-10%, and top-20% review queues using decision curves and expected value. |

### Should Phase 2 train separate sector models?

Separate Utility and Consumer Discretionary models are reasonable **challengers**, but they should
not automatically replace the pooled model. Phase 1 has approximately 30 issuers and roughly
90–100 distinct deterioration episode starts per sector. Quarterly rows do not solve the small-
sample problem because observations from the same company and overlapping future windows are
related. Splitting the data would halve the issuer count available to each model, increase variance,
weaken probability calibration, and make performance differences more sensitive to a few firms.

The recommended comparison is:

1. A pooled benchmark with sector indicators and a small number of financially justified sector
   interactions.
2. A partially pooled or hierarchical model that learns common relationships while allowing some
   coefficients or baselines to differ by sector.
3. A pooled classifier with sector-specific probability calibration and alert thresholds.
4. Fully separate sector models as challengers.

The fully separate models should be promoted only if they improve repeated future-period PR-AUC,
precision, calibration, and stability by more than the uncertainty around those differences. A
useful planning target is at least 75–100 issuers and 150–200 distinct deterioration episodes per
sector, including unsuccessful and delisted firms. This is a planning range, not a universal
statistical rule. Learning curves and issuer-clustered confidence intervals should determine
whether the final sample is sufficient.

### Phase 2 implementation workstreams

#### 1. Expand and strengthen the dataset

- Add delisted, bankrupt, acquired, and financially distressed issuers without using later outcomes
  to decide inclusion.
- Increase issuer and distinct-event counts in both existing sectors before fitting independent
  sector models.
- Preserve filing dates, amended filings, macro vintages, and source lineage under the existing
  point-in-time policy.
- Add sectors only after establishing a valid sector taxonomy, adequate issuer coverage, and an
  economically appropriate KPI definition.
- Create data-quality scores for tag mapping, filing delay, missingness, restatements, and unusual
  denominators; test whether these signals have forward-looking value without leakage.

#### 2. Revisit the outcome without optimizing it after the fact

- Retain the Phase 1 label as the benchmark outcome.
- Pre-register alternative coverage thresholds and two-, four-, and six-quarter horizons.
- Test a multi-KPI outcome that combines debt-service weakness, cash-flow stress, and rising
  leverage, while avoiding a label so complex that it becomes difficult to explain.
- Evaluate discrete-time survival analysis so the model estimates when deterioration may occur and
  properly handles observations whose future outcomes are not yet known.
- Score performance by distinct deterioration episode as well as by company-quarter.

#### 3. Add financially motivated predictors

- Debt structure: debt maturity pressure, short-term debt share, refinancing need, interest-expense
  growth, fixed-charge burden, and debt issuance or repayment.
- Liquidity and cash flow: cash reserves, current-ratio trend, working-capital requirements,
  operating-cash-flow conversion, capital-expenditure burden, and dividend coverage.
- Operating performance: revenue growth, margin trend, earnings volatility, asset turnover, and
  profitability relative to sector peers.
- Market and macro conditions: Treasury-rate changes, investment-grade and high-yield spreads,
  inflation, unemployment, recession indicators, and sector-sensitive measures such as consumer
  confidence or utility financing conditions.
- Temporal features: quarter-over-quarter and year-over-year changes, rolling slopes, volatility,
  drawdowns, distance from company history, and distance from sector norms.
- Require an economic reason, documented availability date, missing-data treatment, and ablation
  result for every retained feature group.

#### 4. Improve forecasts and forecast uncertainty

- Compare random walk and local-level benchmarks with autoregressive, robust trend, and pooled panel
  forecasts by KPI and horizon.
- Model company-level persistence while borrowing information from similar issuers when individual
  histories are short.
- Test seasonal terms only where non-TTM source data show repeatable fiscal-quarter effects; Phase 1
  TTM ratios showed little aggregate seasonality.
- Recalibrate four-quarter prediction intervals and require sector- and horizon-level coverage near
  the stated confidence level.
- Remove forecast-derived classifier features if their incremental out-of-sample value is unstable.

#### 5. Improve classifier performance

- Use nested expanding-window validation for hyperparameter and feature selection.
- Compare regularized logistic regression, constrained gradient boosting, partially pooled sector
  models, discrete-time hazard models, and carefully controlled panel approaches.
- Test class weighting and focal or cost-sensitive objectives; avoid naive row oversampling that
  duplicates correlated quarterly observations and distorts event prevalence.
- Tune the alert policy separately from probability estimation.
- Use company-clustered bootstrap intervals or repeated temporal backtests to determine whether an
  apparent improvement is larger than sampling uncertainty.
- Consider sequence neural networks only after dataset expansion and only if they beat interpretable
  models consistently across sectors, regimes, and future periods.

#### 6. Improve calibration and sector treatment

- Compare pooled, partially pooled, sector-calibrated, and fully separate models using the same
  folds, features, and evaluation periods.
- Test Platt scaling, isotonic calibration, and intercept-only recalibration using training-period
  predictions only.
- Produce reliability charts, calibration error, and Brier decomposition by sector, time period,
  risk band, and company size.
- Examine whether the Utility label needs additional sector context, such as capital-expenditure
  cycles and regulatory cost-recovery timing, rather than assuming weaker ratios equal distress.
- Freeze the chosen sector architecture before opening the new Phase 2 test period.

#### 7. Improve thresholds and analyst usefulness

- Define the relative cost of a missed deterioration event and an unnecessary review.
- Report precision, recall, event capture, and expected workload at the top 5%, 10%, and 20% of
  scores and at any proposed fixed threshold.
- Add decision-curve or expected-value analysis against reviewing every company, reviewing none,
  and random or ratio-only screening.
- Perform analyst case reviews of true positives, false positives, false negatives, and unstable
  predictions to identify missing financial context.
- Run prospective shadow scoring on a fixed schedule before claiming operational usefulness.

#### 8. Improve interpretation, monitoring, and governance

- Provide company-level explanations connecting alerts to source ratios, recent changes, peer
  position, forecasts, macro conditions, and uncertainty.
- Separate predictive association from causal or management-action claims.
- Monitor source freshness, company mix, missingness, feature drift, event rate, ranking, calibration,
  and alert volume.
- Define retraining, recalibration, and escalation triggers before prospective monitoring begins.
- Version the Phase 2 data freeze, label, features, folds, model selection record, threshold policy,
  and final evaluation report.

### Recommended execution order

1. Freeze the Phase 1 release and register the 2023+ holdout as a consumed benchmark.
2. Expand the issuer universe and recover delisted/distressed histories.
3. Rebuild the point-in-time panel and audit new data quality.
4. Pre-register outcome sensitivity tests and a new untouched evaluation period.
5. Establish refreshed naive, logistic, and Phase 1-equivalent baselines.
6. Run feature and forecasting ablations using nested temporal validation.
7. Compare pooled, partially pooled, sector-calibrated, and separate-sector models.
8. Select probability calibration and alert thresholds using development data only.
9. Freeze the complete Phase 2 design and evaluate once on the new test period.
10. Conduct shadow monitoring and publish the Phase 2 model card, data card, and research update.

### Phase 2 acceptance criteria

Phase 2 should be accepted only if it demonstrates:

- stronger and more stable PR-AUC than the 0.397 Phase 1 benchmark across multiple future periods;
- improved precision relative to 0.333 without an unacceptable reduction in the 0.563 recall, or a
  documented cost-based reason for the trade-off;
- reliable sector- and time-specific calibration, assessed alongside the 0.159 Phase 1 Brier score;
- reduced uncertainty and a defensible improvement in Utility ranking and alert precision;
- forecast intervals with observed coverage close to their stated confidence level;
- gains that remain after company-clustered uncertainty analysis and label-sensitivity checks;
- evidence that added forecasts or complex models outperform simpler baselines consistently;
- a documented analyst-review benefit under realistic workload assumptions; and
- one-time evaluation on a genuinely untouched Phase 2 test period.

Power BI remains optional and is not part of the Phase 2 analytical acceptance criteria. If an
interactive interface is revisited, prefer a code-native dashboard that can be versioned and tested
with the Python pipeline unless Power BI is specifically required for a target role or audience.
