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
- Generate documented, Tableau-ready dashboard extracts.

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
- `dashboards/tableau/`: Tableau specifications and ignored generated extracts.

## Reproducibility policy

Generated data and model artifacts are not committed. Each acquisition writes a manifest with
source URL, parameters, retrieval timestamp, checksum, and software version. Configurations,
schemas, transformations, tests, and small fixtures are committed. See
[`docs/reproducibility.md`](docs/reproducibility.md).

## Project status

The full chronological execution plan and completion gates are documented in
[`docs/phase1_implementation_plan.md`](docs/phase1_implementation_plan.md).
The accepted point-in-time, KPI-definition, company-certification, and replacement assumptions are
recorded in
[`docs/decisions/0003-point-in-time-panel-and-modeling-eligibility.md`](docs/decisions/0003-point-in-time-panel-and-modeling-eligibility.md).

Stages 0–18 are complete. The certified universe contains 30 Consumer Discretionary and 30
Utilities companies; all 60 pass the three-KPI coverage, continuity, lineage, and leakage gates.
See
[`docs/stages_0_7_execution.md`](docs/stages_0_7_execution.md) for evidence and limitations.
Stages 8–12, including the 14 audited replacements, frozen deterioration label, publication-grade
EDA, feature registry, and temporal split design, are documented in
[`docs/stages_8_12_execution.md`](docs/stages_8_12_execution.md).
Forecasting, classifier experiments, champion selection, locked-holdout evaluation, and the
production asset graph are documented in
[`docs/stages_13_16_execution.md`](docs/stages_13_16_execution.md) and
[`docs/model_card.md`](docs/model_card.md).
The reconciled four-page Tableau delivery and Phase 1 publication audit are documented in
[`docs/stages_17_18_execution.md`](docs/stages_17_18_execution.md). Open the workbook source at
[`dashboards/tableau/Corporate_Financial_Deterioration.twb`](dashboards/tableau/Corporate_Financial_Deterioration.twb)
after running `make dashboard` to refresh its relative CSV connections. The self-contained packaged
workbook for Tableau Public is
[`dashboards/tableau/Corporate_Financial_Deterioration.twbx`](dashboards/tableau/Corporate_Financial_Deterioration.twbx).
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

Phase 1 is the minimum credible product. Future work may add macroeconomic regime probabilities,
prospective scoring beyond evaluated labels, more sectors, and delisted-company histories under a
new version rather than changing the frozen Phase 1 experiment.
