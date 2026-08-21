# Corporate Financial Deterioration Early-Warning Platform

A point-in-time financial research and machine-learning project that identifies public companies
whose debt-service capacity may deteriorate. The project combines SEC EDGAR fundamentals with
FRED/ALFRED macroeconomic data, forecasts financial KPIs, and ranks companies for analyst review.

This is a screening and research tool—not a bankruptcy model, credit rating, or investment
recommendation.

## Start here

| If you want to... | Start with |
|---|---|
| Read the complete study and final results | **[Combined Phase 1 + Phase 2 research report](reports/publication/Corporate_Financial_Deterioration_Combined_Phase1_Phase2_Research_Report.pdf)** |
| Review the model-optimization evidence | [Phase 2 model optimization and out-of-time results](reports/publication/Phase2_Model_Optimization_and_Out_of_Time_Results.md) |
| Review the project quickly | [Detailed case study](docs/case_study.md) |
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
- Comparison of interpretable logistic models, random forests, histogram gradient boosting,
  support-vector models, pooled and sector-specific XGBoost, and leakage-safe ensembles.
- Probability calibration, sector-specific evaluation, threshold selection, feature stability,
  monitoring, and governance documentation.
- Reproducible Python, DuckDB/Parquet, configuration, tests, and publication evidence.

## What has been completed

Both research phases are complete. Phase 2 expands the Phase 1 population, strengthens the analytical
and interpretability pipeline, improves the model architecture, and completes a sealed late-2024
out-of-time test using outcomes that mature during 2025.

| Workstream | Phase 1 | Phase 2 |
|---|---|---|
| Research universe | Certified 60 issuers across two sectors | Expanded and froze 117 issuers: 75 Consumer Discretionary and 42 Utilities |
| Data engineering | Built filing-aware SEC and vintage-aware FRED/ALFRED pipeline | Rebuilt and reused the expanded point-in-time panel without synthetic or proprietary data |
| Financial features | Standardized coverage, cash-flow, leverage, history, peer, and macro measures | Added liquidity, operating-performance, stability, and leakage-safe issuer-history features with fold-local screening |
| Outcomes | Froze the four-quarter deterioration definition | Preserved the primary outcome and completed a two-quarter sensitivity analysis |
| Forecasting | Compared naive, structural, and dynamic-regression KPI forecasts | Recalibrated forecast intervals and tested forecast-feature value |
| Classification | Compared regularized logistic regression and constrained boosting | Compared interpretable, tree-based, support-vector, pooled/sector-specific, and ensemble architectures |
| Validation | Completed expanding-window development and locked holdout evaluation | Completed nested temporal development, clustered uncertainty, policy testing, and a sealed late-2024 out-of-time test |
| Interpretation and governance | Published figures, source lineage, model card, and execution records | Added feature stability, company explanations, monitoring, uncertainty, and frozen model/threshold evidence |
| Publications | Published the Phase 1 research report | Published the final combined report, Phase 2 research report, recruiter case study, and model-optimization evidence |

The **[combined Phase 1 + Phase 2 research report](reports/publication/Corporate_Financial_Deterioration_Combined_Phase1_Phase2_Research_Report.pdf)**
is the primary final deliverable and includes the latest model evidence. The concise
[optimization results](reports/publication/Phase2_Model_Optimization_and_Out_of_Time_Results.md)
provide a technical supplement. All publications are collected in the
[published reports folder](reports/publication/README.md).

### Phase 1 — reproducible benchmark

Phase 1 established the end-to-end research platform on 60 currently listed US companies across
Consumer Discretionary and Utilities. Its selected gradient-boosted benchmark achieved 0.397
holdout PR-AUC, 0.563 recall, 0.333 precision, 1.97x top-decile lift, and a 0.159 Brier score across
457 observations.

### Phase 2 — expansion, model optimization, and out-of-time test

Phase 2 expanded the frozen active-company sample to 117 issuers (75 Consumer Discretionary and 42
Utilities), strengthened leakage controls, added financially motivated predictors, compared two-
and four-quarter warning horizons, and added model interpretability and monitoring evidence. On
complete four-quarter development out-of-fold predictions, constrained boosting achieved 0.412
PR-AUC versus 0.379 for the partially pooled logistic model.

The subsequent controlled optimization retained the same 117-company population and four-quarter
outcome while comparing five reader-facing model families and multiple static and time-adaptive
ensembles. The frozen 60% pooled / 40% sector-specific XGBoost blend achieved 0.760 development
ROC-AUC and 0.462 development PR-AUC. At the common 80%-recall development policy, its 51.3% alert
rate was lower than the initial Phase 2 model's 57.6%. On the sealed late-2024 test, it achieved **0.841
ROC-AUC**, **0.494 PR-AUC**, and **85.7% recall** with a 51.1% alert rate across 178 observations and
28 events.

The 0.80 ROC-AUC target was achieved, but company-clustered uncertainty remains wide and Utility
recall was 71.4% across only seven events. See the [optimization results](reports/publication/Phase2_Model_Optimization_and_Out_of_Time_Results.md)
and [methodology](docs/phase2_model_optimization_methodology.md).

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

Once the certified Phase 2 panel exists locally, reproduce the Phase 2 development and
model-optimization analyses with:

```bash
make reproduce-phase2-analysis
make reproduce-phase2-model-optimization
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
