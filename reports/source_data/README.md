# Publication source data

These compact Parquet tables preserve the certified Phase 1 evidence used by
`scripts/generate_publication_report.py`. They keep the published Phase 1 report reproducible
without requiring raw SEC/FRED downloads or a separate reporting application.

| File | Contents |
|---|---|
| `phase1_portfolio_snapshot.parquet` | Latest sector-level portfolio summary |
| `phase1_company_watchlist.parquet` | Latest evaluated company-level predictions and financial context |
| `phase1_model_performance.parquet` | Development and locked-holdout model metrics |
| `phase1_company_history.parquet` | Certified company-quarter KPI and prediction history |
| `phase3_final_metrics.json` | Frozen Phase 2 model-optimization and sealed-test metrics with uncertainty intervals; filename retained for internal lineage |

The tables contain derived public-data research evidence only. They contain no credentials,
proprietary data, or synthetic observations. Generated Phase 2 analytical files remain ignored
because they can be reconstructed from the certified local pipeline.
