# Stages 17-18 Execution Record

## Stage 17 - Power BI delivery

Stage 17 now targets Power BI rather than Tableau. Four deterministic analytical interfaces are
derived from certified processed data: Portfolio Overview (snapshot-sector), Analyst Watchlist
(latest evaluated prediction per CIK), Company Detail History (3,150 unique company-fiscal-quarter
decision keys), and Model Performance (model/fold/sector metric grain). Development scores are
out-of-fold; final holdout results are labeled separately; training/history observations without a
valid out-of-sample prediction remain unscored.

The certified Excel interface contains four named tables with 2, 60, 3,150, and 93 rows. The PBIX
embeds a data model, defines exactly Portfolio Overview, Analyst Watchlist, Company Detail, and
Model Performance, and was saved, closed, and reopened in Power BI Desktop 2.156.951.0. Its
relationships implement sector-to-watchlist and company-to-history one-to-many filtering while
leaving model performance disconnected at its separate grain.

Headline reconciliation from the certified package is 60 monitored companies, 22 alerts, 36.67%
alert rate, 28.13% average risk, and 6 Severe-risk companies. Interest coverage is a multiple;
margins, leverage, rates, and probabilities are percentages. The score is financial-deterioration
risk, not bankruptcy or default probability.

### Visual acceptance status

Static inspection of the embedded `Report/Layout` proves that the four pages and many bound cards,
tables, and slicers exist. Inspection of the supplied 2,850 x 1,200 screenshots also found
unpopulated placeholder charts/tables on all four pages. Therefore the model and KPI contract are
accepted as analytically reproducible, while presentation readiness remains explicitly open. A
final Windows Power BI Desktop pass must bind or remove placeholders, apply polished titles/theme
and accessibility metadata, and recapture evidence. The VM used for authoring was fully stopped on
5 August 2026 after the artifacts were transferred, eliminating its active CPU/RAM allocation.

## Stage 18 - reproduction, publication, and release audit

Stage 18 was migrated from Tableau-specific XML/package checks to Power BI package validation. The
audit verifies the four exported interfaces, reconciliation results, required PBIX members,
embedded `DataModel`, exact page-name set, four screenshots, validation notes, dependency lock,
environment template, source manifests, frozen champion, locked-holdout evidence, publication
documents, and targeted credentials/local-path scans. Release hashes now cover the certified XLSX
and PBIX alongside scope, universe, label, modeling, and champion-selection artifacts.

The publication report adds an experimental-design narrative covering the estimand, eligibility
rules, point-in-time controls, label construction, KPI economics, time-series model selection,
classifier choice, imbalance-aware metrics, temporal validation, results, limitations, and a Phase
2 roadmap. Every analytical chart is regenerated from the certified workbook; claims are bounded
to the observed 60-company, two-sector experiment.

## Completion and reproduction evidence

Run the following in an environment containing the retained processed store and manifests:

```bash
make check
.venv/bin/cfd verify-source-manifests
.venv/bin/cfd run-stages-17-18
```

The repository intentionally does not commit raw/intermediate/processed data, credentials,
machine-local paths, caches, or Power BI lock files. The source code can reproduce analytical
interfaces from the certified local store; the versioned XLSX/PBIX and publication artifacts
provide the public Phase 1 evidence package. Presentation-level Power BI completion remains a
Phase 2 acceptance item until the placeholder findings above are resolved.
