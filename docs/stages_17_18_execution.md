# Stages 17–18 Execution Record

## Stage 17 — Tableau delivery

Stage 17 creates four deterministic CSV interfaces from certified processed data. Portfolio
Overview contains one row per snapshot and sector; Company Watchlist contains the latest evaluated
prediction per CIK; Company Detail History contains all 3,150 fiscal-period decision keys; Model
Performance contains model/fold/sector metrics. Development performance and displayed development
probabilities are strictly out of fold. The final holdout remains separately labeled, and training
history has null scores rather than in-sample predictions.

The workbook defines four pages: Portfolio Overview, Analyst Watchlist, Company Detail, and Model
Performance. Filters cover sector, industry, company, period, alert, risk band, model, feature set,
fold, and evaluation sample. Leverage is formatted as a percentage; interest coverage is a multiple.
Every alert is described as deterioration risk, never bankruptcy or default probability.

`tableau_reconciliation.csv` verifies unique output grains, bounded probabilities, all 60 companies,
portfolio alert totals, exact KPI joins, and OOF labeling. The export process contains no network
calls, credentials, raw filing payloads, or machine-local paths.

## Stage 18 — Reproduction and release audit

Stage 18 checks the four extracts, reconciliation results, parseable workbook XML, dependency lock,
environment template, source manifests, champion artifact, holdout evidence, all publication
documents, and a targeted credentials/local-path scan. It records hashes for scope, universe,
label, modeling, dashboard contract, frozen champion, and workbook sources.

The full cached-data rebuild entry point is `make reproduce-phase1`. It first runs configuration,
lint, type, Dagster-definition, and non-network test gates; then rebuilds the certified panel and
EDA, forecasts and classifiers, dashboard extracts, and final release checks. Network acquisition
remains separate because it is rate-limited and already protected by immutable cache manifests.

## Completion evidence

Completion requires `make check`, `cfd verify-source-manifests`, `cfd run-stages-17-18`, and a clean
git secret/path inspection to pass in the intended environment. Generated summaries under
`reports/generated/` provide row counts and individual audit evidence. The repository tag
`v1.0.0-phase1` identifies the release after all gates pass.
