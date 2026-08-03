# Stages 0–7 Execution Record

**Completed:** 2026-08-02
**Selection version:** `selected-universe-v1`
**Random seed:** `20260802`
**Universe date:** 2026-08-02
**Financial history cutoff:** 2025-12-31

## Gate results

| Stage | Result | Authoritative evidence |
|---|---|---|
| 0 — Analytical contract | Complete | Versioned scope, universe, label, feature, SIC, and XBRL mapping identifiers validate successfully |
| 1 — Source proof | Complete | Nine issuers, two ALFRED patterns, and SEC bulk reconciliation for 2012Q1, 2020Q2, and 2025Q4 |
| 2 — Architecture/contracts | Complete | Six persisted table contracts, controlled reason codes, Dagster graph, DuckDB marts, and Parquet outputs |
| 3 — Candidate universe | Complete | 303 mapped current issuers; 135 rules-based candidates: 75 Consumer Discretionary and 60 Utilities |
| 4 — Historical ingestion | Complete | 269,412 accession-aware financial facts and 13,456 observations across six macro series |
| 5 — Fiscal normalization | Complete | 73,987 normalized concept-quarter rows, 6,856 company-quarter rows, and zero duplicate grain keys |
| 6 — Eligibility | Complete | 65 eligible companies: 31 Consumer Discretionary and 34 Utilities |
| 7 — Selection | Complete | 60 selected companies, five reserves, exact 30/30 sector balance, deterministic reproduction |

All 198 cached source artifacts passed checksum and byte-count verification. All six persisted
tables passed their required-column and primary-key uniqueness contracts.

Machine-readable local evidence is generated at
`reports/generated/stages_0_7_summary.json`. The underlying raw and processed data are ignored by
Git and are recreated with `cfd run-stages-0-7`.

## Source proof and reconciliation

The proof set contains five Consumer Discretionary and four Utilities issuers, including
non-calendar fiscal years and different financial profiles. SEC Company Facts accessions were
reconciled to quarterly Financial Statement Data Sets:

| Bulk quarter | Proof-company filings | Matched Company Facts accessions |
|---|---:|---:|
| 2012Q1 | 9 | 9 |
| 2020Q2 | 9 | 9 |
| 2025Q4 | 11 | 10 |

The unmatched 2025Q4 filing remains visible in the audit rather than being silently removed.
Filing dates, accession numbers, fiscal periods, units, observation dates, and ALFRED real-time
fields are retained.

## Data-quality findings and resolutions

1. The initial fiscal-quarter implementation omitted CIK from a grouping key. A regression test
   now proves that separate companies cannot collapse into the same concept-period row.
2. SEC XBRL tags are case-sensitive. Additional tested mappings were added for interest expense,
   revenue, operating cash flow, and capital expenditure variants.
3. Recently listed issuers consumed the random candidate pool despite being unable to meet the
   history gate. A preliminary, outcome-independent filing-history screen now requires at least
   16 distinct 10-Q periods and six 10-K periods by the financial cutoff.
4. SIC 4922–4924 mixed regulated gas distributors with pipelines, midstream partnerships, and LNG
   infrastructure. Versioned entity overrides exclude non-regulated energy infrastructure.
5. Tennessee Valley Authority was excluded because its exchange-traded instrument is debt rather
   than public common equity.
6. Dollar General and BJ’s Wholesale were excluded from the cyclical sector because their business
   mix is staples-oriented despite broad SIC retail classifications.

All corrections were based on source structure, company eligibility, or business classification
before deterioration-label construction or model performance inspection.

## Eligibility evidence

Eligible companies satisfy all prespecified gates:

- At least 24 usable fiscal quarters.
- At least 16 consecutive usable quarters.
- At least 80% core-field coverage.
- At least 12 quarters with economically meaningful interest expense.

The selected universe and deterministic reserve order are frozen in
[`../configs/selected_universe.yml`](../configs/selected_universe.yml). The manifest excludes API
credentials and generated financial values.

## Known limitations carried forward

- The universe contains companies current as of 2026-08-02 and therefore retains the documented
  survivorship limitation.
- Financial facts stop at the configured 2025-12-31 cutoff.
- SIC is not equivalent to GICS; versioned business-classification overrides are necessary.
- One candidate Company Facts request failed and remains documented in the generated failure log.
- Five currently eligible reserves are available. Expansion beyond 65 companies would require a
  documented enlargement of the candidate pool using the same seed and rules.
- The deterioration label has not been constructed or inspected; that begins after the Stage 8
  point-in-time analytical panel.

## Reproduction

```bash
cp .env.example .env
# Configure SEC_USER_AGENT and FRED_API_KEY locally.
make bootstrap
# Only for an intentional future universe rebuild:
.venv/bin/cfd run-stages-0-7 --refresh-universe
.venv/bin/cfd verify-source-manifests
make check
```

Raw downloads are cached and checksummed, so reruns reuse unchanged source files while rebuilding
all normalized, eligibility, and selection outputs.

## Post-selection local financial store

After the selection is frozen, `cfd materialize-final-store` filters the canonical financial-fact,
fiscal-quarter, and company-quarter Parquet tables to the 60 selected CIKs and refreshes their
DuckDB marts. It retains one raw SEC Company Facts response per selected company and removes raw
Company Facts for rejected candidates, reserves, and redundant proof samples. Issuer submissions
and universe metadata remain available because they contain the evidence needed to explain the
selection; they are not used as the downstream financial modeling store.

The command performs no API calls. A deliberate future universe refresh must rerun the broad
eligibility workflow with `cfd run-stages-0-7 --refresh-universe` before materializing a newly
frozen final store. Without that explicit flag, the command stops before ingestion to prevent
accidental candidate-history API calls.
