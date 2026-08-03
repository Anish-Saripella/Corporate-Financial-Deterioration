# ADR 0002: Public-source ingestion strategy

**Status:** Accepted
**Date:** 2026-08-02

## Decision

Use the SEC bulk submissions archive to construct the current issuer universe, candidate-specific
Company Facts JSON for full 2012–2025 financial histories, and selected quarterly Financial
Statement Data Set archives for accession-level reconciliation. Use initial-release ALFRED
observations for revised macroeconomic series and a single current vintage for non-revised daily
series.

## Rationale

Downloading every quarterly Financial Statement Data Set would add several gigabytes while still
requiring issuer-specific normalization. Company Facts retains accession, filing date, fiscal
period, unit, and XBRL context for the selected candidate population. Reconciliation against
2012Q1, 2020Q2, and 2025Q4 bulk datasets verifies common accessions across the study period.

## Consequences

The pipeline remains free, reproducible, filing-aware, and materially smaller. Company-specific
tag mapping and amendments remain explicit. The complete all-filer submissions archive is cached
locally but excluded from Git.
