# Corporate Financial Deterioration Early-Warning Platform

A point-in-time financial research and machine-learning project that identifies public companies
whose debt-service capacity may deteriorate. The project combines SEC EDGAR fundamentals with
FRED/ALFRED macroeconomic data, forecasts financial KPIs, and ranks companies for analyst review.

This is a screening and research tool—not a bankruptcy model, credit rating, or investment
recommendation.

## Start here

| If you want to... | Start with |
|---|---|
| Read the latest results | **[Phase 3 model accuracy and ensemble results](reports/publication/Phase3_Model_Accuracy_and_Ensemble_Results.md)** |
| Read the complete Phase 1 + 2 study | [Combined research report](reports/publication/Corporate_Financial_Deterioration_Combined_Phase1_Phase2_Research_Report.pdf) |
| Review the project quickly | [Phase 2 portfolio case study](reports/publication/Corporate_Financial_Deterioration_Phase2_Portfolio_Case_Study.pdf) |
| Browse every published deliverable | [Published reports index](reports/publication/README.md) |
| Understand the system design | [Architecture](docs/architecture.md) and [modeling lineage](docs/modeling_lineage.md) |
| Reproduce the analysis | [Phase 1 guide](docs/reproducibility.md) and [Phase 2 guide](docs/phase2_reproducibility.md) |
| Prepare for an interview | [Resume and interview summary](docs/resume_summary.md) |

## What the project demonstrates

- Point-in-time ingestion of public SEC and FRED/ALFRED data with source manifests and checksums.
- Fiscal-quarter normalization that retains filing dates, amendments, and availability lineage.
- Financial KPI engineering for interest coverage, free-cash-flow margin, leverage, liquidity,
  operating performance, and peer-relative trends.
- Expanding-window validation designed to prevent future-data leakage.
- Comparison of interpretable logistic models, random forests, Extra Trees, support-vector models,
  pooled and sector-specific XGBoost, and leakage-safe ensembles.
- Probability calibration, sector-specific evaluation, threshold selection, feature stability,
  monitoring, and governance documentation.
- Reproducible Python, DuckDB/Parquet, configuration, tests, and publication evidence.

## What has been completed

All three research phases are complete. Phase 3 preserves the Phase 2 population and label, improves
the model architecture, and completes a sealed late-2024 out-of-time test using outcomes that mature
during 2025.

| Workstream | Phase 1 | Phase 2 | Phase 3 |
|---|---|---|---|
| Research universe | Certified 60 issuers across two sectors | Expanded and froze 117 issuers: 75 Consumer Discretionary and 42 Utilities | Preserved the Phase 2 population for a controlled model comparison |
| Data engineering | Built filing-aware SEC and vintage-aware FRED/ALFRED pipeline | Rebuilt the expanded point-in-time panel with stricter eligibility and data-quality controls | Reused the frozen point-in-time panel without synthetic or proprietary data |
| Financial features | Standardized coverage, cash-flow, leverage, history, peer, and macro measures | Added liquidity, operating-performance, stability, and leakage-safe temporal features | Screened features inside each training fold and added leakage-safe issuer history |
| Outcomes | Froze the four-quarter deterioration definition | Preserved the primary outcome and completed a two-quarter sensitivity analysis | Preserved the four-quarter definition for direct comparison |
| Forecasting | Compared naive, structural, and dynamic-regression KPI forecasts | Recalibrated forecast intervals and tested forecast-feature value | Focused on classification and ensemble accuracy rather than adding a new forecast task |
| Classification | Compared regularized logistic regression and constrained boosting | Compared pooled, partially pooled, and constrained boosted architectures | Compared six families plus static, adaptive, stacked, and pooled/sector ensembles |
| Validation | Completed expanding-window development and locked holdout evaluation | Completed nested temporal validation, clustered uncertainty, episode analysis, calibration, and policy testing | Completed rolling development and a sealed late-2024 out-of-time test |
| Interpretation and governance | Published figures, source lineage, model card, and execution records | Added feature stability, company explanations, monitoring, readiness, and analyst-review evidence | Froze the champion, thresholds, and configuration before opening the test |
| Publications | Published the Phase 1 research report | Published the Phase 2 report, recruiter case study, and combined Phase 1 + Phase 2 report | Published the Phase 3 methodology, exact metrics, and results summary |

The **[Phase 3 results](reports/publication/Phase3_Model_Accuracy_and_Ensemble_Results.md)** provide
the latest model evidence. The **[combined Phase 1 + Phase 2 research report](reports/publication/Corporate_Financial_Deterioration_Combined_Phase1_Phase2_Research_Report.pdf)**
provides the full research foundation. All publications are collected in the
[published reports folder](reports/publication/README.md).

### Phase 1 — reproducible benchmark

Phase 1 established the end-to-end research platform on 60 currently listed US companies across
Consumer Discretionary and Utilities. Its selected gradient-boosted benchmark achieved 0.397
holdout PR-AUC, 0.563 recall, 0.333 precision, 1.97x top-decile lift, and a 0.159 Brier score across
457 observations.

### Phase 2 — expanded development study

Phase 2 expanded the frozen active-company sample to 117 issuers (75 Consumer Discretionary and 42
Utilities), strengthened leakage controls, added financially motivated predictors, compared two-
and four-quarter warning horizons, and added model interpretability and monitoring evidence. On
complete four-quarter development out-of-fold predictions, constrained boosting achieved 0.412
PR-AUC versus 0.379 for the partially pooled logistic model.

Phase 2 results remain development evidence. Phase 3 adds a separate sealed late-2024 test whose
four-quarter outcomes mature during 2025; decisions initiated during 2025 still lack complete
four-quarter outcomes and remain unavailable for a later prospective evaluation.

### Phase 3 — model accuracy and sealed out-of-time test

Phase 3 compared six model families and multiple static and time-adaptive ensembles without changing
the 117-company population. The frozen 60% pooled / 40% sector-specific XGBoost blend achieved 0.760
development ROC-AUC and 0.462 development PR-AUC. At the common 80%-recall development policy, its
51.3% alert rate was lower than Phase 2's 57.6%. On the sealed late-2024 test, it achieved **0.841
ROC-AUC**, **0.494 PR-AUC**, and **85.7% recall** with a 51.1% alert rate across 178 observations and
28 events.

The 0.80 ROC-AUC target was achieved, but company-clustered uncertainty remains wide and Utility
recall was 71.4% across only seven events. See the [Phase 3 results](reports/publication/Phase3_Model_Accuracy_and_Ensemble_Results.md)
and [methodology](docs/phase3_methodology.md).

Dagster represents the completed Phase 1 asset graph. Phase 2 is reproduced through deterministic,
fail-fast CLI stages; the repository does not claim that the Phase 2 workflow is fully represented
as Dagster assets.

See the [combined report](reports/publication/Corporate_Financial_Deterioration_Combined_Phase1_Phase2_Research_Report.pdf)
for interpretation, limitations, and the complete comparison.

## Repository map

```text
.
├── reports/publication/  Published recruiter- and research-facing reports
├── docs/                 Technical documentation, governance, and execution records
├── src/cfd/              Reusable ingestion, feature, modeling, and evaluation code
├── configs/              Versioned research, data, feature, and modeling decisions
├── tests/                Unit and integration tests
├── sql/                  Versioned DuckDB transformations
├── scripts/              Publication-generation scripts
├── data/                 Local data locations; generated data is not committed
├── reports/source_data/  Certified evidence used by publication generators
└── reports/figures/      Reproducible figures supporting the published reports
```

The [documentation index](docs/README.md) groups detailed material by purpose instead of requiring
readers to infer an order from filenames.

## Reproduce locally

Requirements: Python 3.12, Git, `make`, and internet access for initial installation and source-data
ingestion.

```bash
cp .env.example .env
# Add SEC_USER_AGENT and FRED_API_KEY to .env
make bootstrap
make check
```

The `.env` file and generated source/model data are intentionally excluded from Git. Phase 1 can be
rebuilt from a certified local public-data cache with:

```bash
make reproduce-phase1
```

Once the certified Phase 2 panel exists locally, reproduce the Phase 2 development analysis with:

```bash
make reproduce-phase2-analysis
```

Acquisition is deliberately separate from validation. Follow the [data-source register](docs/data_sources.md)
and the phase-specific reproducibility guides for required credentials, ordered stages, expected
outputs, and data-publication restrictions.

## Important scope limits

- The target is deterioration in interest-payment capacity, not bankruptcy or default.
- The sample contains currently active companies and therefore has survivorship bias.
- Results cover two US sectors and should not be generalized to the full credit market.
- Adjacent quarterly outcomes overlap; company- and episode-level evidence is used to avoid
  treating every row as an independent experiment.
- The system prioritizes analyst screening and does not automate a lending or investment decision.

Full assumptions are documented in [assumptions and limitations](docs/assumptions_and_limitations.md),
the [Phase 1 model card](docs/model_card.md), and the [Phase 2 methodology](docs/phase2_methodology.md).

## License

Released under the [MIT License](LICENSE).
