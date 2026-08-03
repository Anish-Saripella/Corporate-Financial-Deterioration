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

## First reproducible workflow

```bash
.venv/bin/cfd validate-config
.venv/bin/cfd show-scope
.venv/bin/dagster asset materialize -m cfd.orchestration.definitions \
  --select phase1_configuration,local_duckdb
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

Infrastructure and data contracts are established. The next milestone is a filing-aware SEC
proof of concept for 6–10 companies, followed by the rules-based 60-company universe audit.
