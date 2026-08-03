# Company Universe Policy

## Population and selection date

The project studies a fixed universe of currently listed US operating companies as of
2025-12-31. It targets 30 Consumer Discretionary and 30 Utilities issuers after screening a
rules-based candidate universe.

## Eligibility

- Listed on NYSE, NASDAQ, or NYSE American.
- Files 10-K and 10-Q reports as a US domestic operating issuer.
- At least 24 usable quarters and 16 consecutive quarters before the first prediction.
- At least 80% coverage of core accounting fields.
- Sufficient, economically meaningful interest expense history for the primary outcome.

## Exclusions

- Delisted companies, funds, ETFs, SPAC shells, foreign private issuers, banks, and insurers.
- Issuers whose essential XBRL histories cannot be normalized defensibly.
- Exclusions based on later model performance or whether a company experiences deterioration.

Every candidate receives `included`, a controlled `reason_code`, and supporting evidence in the
universe audit table.

## Known limitation

Excluding delisted issuers creates survivorship and selection bias. Event prevalence may be
lower, and results do not estimate default or deterioration risk for the historical population
of all public firms. All model claims are limited to the fixed research universe. This tradeoff
is accepted to keep Phase 1 reproducible with consistent free public data.
