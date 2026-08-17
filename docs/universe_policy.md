# Company Universe Policy

## Population and selection date

The project studies a fixed universe of currently listed US operating companies as of
2026-08-02, using financial history through 2025-12-31. It targets 30 Consumer Discretionary and
30 Utilities issuers after screening a rules-based candidate universe.

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

## Reproducible sampling

After applying all eligibility rules, select companies by stratified random sampling without
replacement using the Phase 1 project seed `20260802`. Stratify by sector, broad industry, and three
filing-derived size tiers based primarily on median total assets during the development period.
Maintain a deterministic reserve order.

Before modeling, Stage 8 applies stricter company-level certification to all three required KPIs.
Each company must pass the same coverage, continuity, mapping, lineage, and point-in-time rules.
Failure of any KPI triggers replacement by the next same-sector reserve; KPI-specific modeling
subsets are not used. Each replacement must pass identical rules and produce a versioned audit
record. If reserves are insufficient, expand the candidate pool transparently rather than lowering
standards.

Stage 8 produced universe version `selected-universe-v2-certified`. Fourteen original selections
failed at least one strict KPI gate. Four frozen reserves and ten companies from the deterministic
expanded candidate order replaced them within the same sector. The final universe has 30 issuers
per sector, all 60 pass every KPI and lineage rule, and no unused reserve remains. The complete
before/after evidence is generated as `reports/generated/universe_replacements.csv`.

Do not change the seed or redraw the sample because of outcome prevalence or model performance.
If the frozen selection produces an infeasible event count, expand the sample using the reserve
order up to a maximum of 80 companies and document the scope change. Do not redraw the original
sample or search for a different random seed.

## Known limitation

Excluding delisted issuers creates survivorship and selection bias. Event prevalence may be
lower, and results do not estimate default or deterioration risk for the historical population
of all public firms. All model claims are limited to the fixed research universe. This tradeoff
is accepted to keep Phase 1 reproducible with consistent free public data.
