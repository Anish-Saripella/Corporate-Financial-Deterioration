# Phase 2 Reproducibility Guide

## Environment

Phase 2 uses Python 3.12, dependencies declared in `pyproject.toml`, and the locked resolution in
`uv.lock`.

```bash
cp .env.example .env
# Replace only the placeholders in the local .env file.
make bootstrap
make check
```

The `.env` file is ignored by Git. Never place an SEC identity, email address, FRED key, or other
credential in source code, configuration, reports, notebooks, screenshots, or committed logs.

## Public data sources

- SEC EDGAR company submissions, company facts, and filing metadata supply financial statements,
  issuer identifiers, filing dates, and amendment lineage.
- FRED/ALFRED supplies public macroeconomic observations and vintage-aware availability dates.
- The project does not use proprietary or synthetic data.

Automated SEC requests must use the researcher's own descriptive `SEC_USER_AGENT`. FRED requests
use the researcher's own `FRED_API_KEY`. `.env.example` contains placeholders only.

## Full ordered workflow

Phase 2 is executed through the ordered CLI stages below. Dagster currently represents the Phase 1
asset graph; it does not orchestrate the complete Phase 2 workflow.

The candidate-ingestion steps require network access and valid local credentials:

```bash
.venv/bin/cfd validate-config
.venv/bin/cfd build-phase2-eligibility
.venv/bin/cfd freeze-phase2-universe
.venv/bin/cfd build-phase2-panel
.venv/bin/cfd audit-phase2-readiness
make reproduce-phase2-analysis
```

The frozen design uses selection date 2026-08-02, financial cutoff 2025-12-31, active issuers
only, and deterministic randomization. `configs/phase2.yml` is authoritative. Sampling is seeded,
stratified, random sampling without replacement after eligibility screening. Model training gives
each sector equal aggregate weight.

## Analysis-only workflow

When the certified local Phase 2 panel already exists:

```bash
make reproduce-phase2-analysis
```

This executes, in order:

1. Four-quarter development models and fold-local feature selection.
2. Out-of-fold model evidence.
3. KPI forecast backtests and interval recalibration.
4. Interpretability, thresholds, monitoring, and model/data cards.
5. Paired two-quarter versus four-quarter sensitivity analysis.
6. Development research report and publication documents.

## Reproducibility seeds

- Universe randomization lineage: seed 42, encoded deterministically in the configured Phase 2
  sampler.
- Feature selection and model fitting: `20260802`.
- Company-clustered bootstrap: `20260805`.

The completed Stage 24 run retained all 117 selected companies, assigned 37 companies to the
retained-with-quality-flag tier, and made zero reserve replacements. The frozen reserve order is
lineage for a future universe revision, not evidence that replacements occurred in this run.

Seeds make reruns deterministic against identical source artifacts and software. They do not make
live source APIs immutable; source manifests and checksums provide that audit trail.

## Expected generated outputs

Core evidence includes:

- `data/processed/phase2_point_in_time_panel.parquet`
- `data/processed/phase2_oof_predictions.parquet`
- `data/processed/phase2_horizon_oof_predictions.parquet`
- `reports/generated/phase2_metrics.csv`
- `reports/generated/phase2_recall_first_threshold_table.csv`
- `reports/generated/phase2_horizon_comparison.csv`
- `reports/generated/phase2_horizon_clustered_differences.csv`
- `reports/generated/phase2_company_case_studies.csv`
- `reports/publication/Corporate_Financial_Deterioration_Phase2_Research_Report.docx`
- `reports/publication/Corporate_Financial_Deterioration_Phase2_Research_Report.pdf`
- `reports/publication/Corporate_Financial_Deterioration_Phase2_Portfolio_Case_Study.docx`
- `reports/publication/Corporate_Financial_Deterioration_Phase2_Portfolio_Case_Study.pdf`

Generated CSV/Parquet files are ignored because they can contain large transformed datasets and
can be rebuilt from the local public-data cache. Publication reports, configurations, source code,
tests, and documentation are suitable for version control after a credential scan.

## Data that must not be committed

- `.env` and all real API credentials.
- Raw SEC/FRED responses and large intermediate/processed datasets.
- Local DuckDB databases, model binaries, caches, and API request logs.
- Any artifact containing an unredacted local credential or personal SEC contact information.

Raw public responses are excluded for repository size, rate-limit, and reproducible-lineage
reasons—not because the project used private financial data. Manifests record retrieval metadata
and checksums without storing secrets.

## Quality gate

```bash
make check
```

The gate validates configuration, formatting, lint rules, static types, the orchestration graph,
and non-network automated tests. The horizon sensitivity stage additionally verifies that no final
future test was opened and records `synthetic_data_used: false`.

## Interpretation boundary

The 2023-and-later Phase 1 holdout has already been examined and is now development evidence. Do
not describe Phase 2 metrics as a final untouched test. The final post-2025 test can be evaluated
only after its four-quarter outcomes mature and the model, calibration, and threshold policy are
frozen.
