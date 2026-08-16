# Corporate Financial Deterioration Early-Warning Platform

A point-in-time financial research and machine-learning project that identifies public companies
whose debt-service capacity may deteriorate. The project combines SEC EDGAR fundamentals with
FRED/ALFRED macroeconomic data, forecasts financial KPIs, and ranks companies for analyst review.

This is a screening and research tool—not a bankruptcy model, credit rating, or investment
recommendation.

## Start here

| If you want to... | Start with |
|---|---|
| Read the completed study | **[Combined Phase 1 + Phase 2 research report](reports/publication/Corporate_Financial_Deterioration_Combined_Phase1_Phase2_Research_Report.pdf)** |
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
- Comparison of interpretable logistic models, constrained gradient boosting, and financial KPI
  forecasting baselines.
- Probability calibration, sector-specific evaluation, threshold selection, feature stability,
  monitoring, and governance documentation.
- Reproducible Python, DuckDB/Parquet, configuration, tests, and optional Power BI evidence.

## Completed phases

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

Phase 2 results are development evidence. The post-2025 future test remains unopened until its
four-quarter outcomes mature, so the repository does not claim final prospective performance.

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
├── dashboards/           Optional Power BI prototype and supporting evidence
├── scripts/              Publication-generation scripts
├── data/                 Local data locations; generated data is not committed
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
