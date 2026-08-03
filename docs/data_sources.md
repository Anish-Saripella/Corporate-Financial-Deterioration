# Data Source Register

## SEC EDGAR

Uses:

- Issuer identity, CIK, ticker, exchange, SIC, and filing history.
- As-filed XBRL financial facts and filing/accession metadata.
- Historical bulk financial statement datasets for efficient initial ingestion.

Controls:

- Send an identifying `SEC_USER_AGENT` containing a real contact email.
- Prefer bulk archives and cache every response.
- This repository caps automated calls at five requests per second, below the SEC's published
  maximum of ten.
- Retry transient failures with bounded exponential backoff.
- Store raw bytes unchanged with retrieval metadata and SHA-256 checksums.
- Never infer information availability from `period_end`; use filing acceptance/availability.

Primary documentation:

- https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- https://www.sec.gov/file/financial-statement-data-sets
- https://www.sec.gov/filergroup/announcements-old/new-rate-control-limits

## FRED/ALFRED

Uses:

- Rates, yield spread, credit spread, unemployment, industrial production, and retail sales.
- Historical real-time periods for revised series.

Controls:

- A free `FRED_API_KEY` is required for ingestion.
- API keys are never written to acquisition manifests or committed files.
- Preserve observation date, `realtime_start`, and `realtime_end`.
- Revised series use historical vintages; current revised values cannot enter old decisions.

Primary documentation:

- https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- https://fred.stlouisfed.org/docs/api/fred/realtime_period.html

## Licensing and publication

Only free public sources are permitted in Phase 1. Public availability does not imply permission
to republish every raw file. The public repository contains code, configurations, manifests,
small tests, and derived non-sensitive outputs. Large raw downloads remain ignored and are
recreated through documented source requests.
