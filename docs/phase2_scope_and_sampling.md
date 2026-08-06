# Phase 2 Scope and Sampling Specification

## Confirmed research population

Phase 2 studies companies that are active at the frozen selection date. It retains the two Phase 1
sectors—Consumer Discretionary and Utilities—and uses 75 Consumer Discretionary and 42 Utility
issuers. Delisted companies remain excluded by design.

The revised real SEC audit found 82 Consumer Discretionary and 42 Utility issuers with reliable
interest-coverage histories. The confirmed draw uses 75 Consumer issuers, preserves seven Consumer
reserves, and uses all 42 eligible Utilities. The imbalance is retained rather than discarding 33
eligible Consumer companies solely to force equal sector counts. Each sector receives equal total
weight during model fitting, and all performance results are reported separately by sector.

This is a deliberate scope choice, not a correction for survivorship bias. Results describe the
selected population of surviving public issuers. They must not be interpreted as default-risk
estimates for all companies that existed historically. In particular, event prevalence and model
performance may look better than they would in a population that includes failed firms.

The selection date is frozen at August 2, 2026, and financial history ends on December 31, 2025.
These are the same cutoffs used in Phase 1, so changes in results are not caused by extending the
information window.

## How companies are assigned to sectors

The SEC assigns each issuer a four-digit Standard Industrial Classification (SIC) code. The project
maps that code through the controlled rules in `configs/sic_mapping.yml`:

- SIC 4911 maps to Utilities / Electric Utilities.
- SIC 5812 and 5813 map to Consumer Discretionary / Restaurants.
- Other listed SIC codes map to the documented broad industries for utilities, durable goods,
  automobiles, apparel, retail, lodging, restaurants, and recreation.

An issuer outside these mappings is not forced into either sector. The project also maintains
explicit exclusions for economically misleading edge cases. Grocery-oriented discount retailers
are excluded from Consumer Discretionary, and non-regulated pipelines, midstream partnerships, and
LNG infrastructure are excluded from Utilities. These rules are determined before labels or model
results are examined.

SIC is a reproducible public classification, but it is imperfect: diversified companies can have
activities outside their primary SIC. The mapping therefore supports consistent research strata;
it should not be treated as a complete description of every business segment.

## Sampling procedure inherited from Phase 1

1. Construct the active US operating-company population from SEC submissions.
2. Retain NYSE, NASDAQ, and NYSE American issuers that file domestic 10-K and 10-Q reports.
3. Exclude funds, ETFs, SPAC shells, foreign private issuers, banks, insurers, explicitly mapped
   non-scope entities, and issuers with unusable XBRL histories.
4. Require at least 16 usable interest-coverage quarters, one run of eight consecutive usable
   interest-coverage quarters, and 12 quarters with total-assets history. Occasional gaps in
   optional predictors are allowed.
5. Preserve strict filing-time lineage and point-in-time availability rules.
6. Assign three within-sector size tiers using median development-period total assets, with median
   revenue as the documented tie-breaker.
7. Sample without replacement across broad-industry and size-tier strata.
8. Use seed `42`. The implementation converts the seed and CIK into a deterministic hash;
   rerunning the same frozen inputs therefore reproduces the same order.
9. Rank all mapped active candidates. After eligibility is established, select 75 Consumer
   Discretionary and 42 Utility issuers using the seeded stratified procedure.
10. Freeze all remaining eligible issuers in a same-sector reserve order before examining outcomes
   or model performance.
11. Never redraw or replace an issuer because of deterioration prevalence, a label, a prediction,
    or its effect on model performance.
12. Treat the former all-KPI company certification as a quality tier. Modeling eligibility is
    evaluated at the company-quarter level. A label requires four consecutive future fiscal
    quarters; optional predictors receive training-fold imputation and missingness indicators.
13. Evaluate forecast eligibility separately for each company, KPI, origin, and horizon.

## Why stratification is used

A simple random draw could overrepresent the largest electric utilities or one retail industry.
Industry and size stratification improves coverage of distinct operating economics while retaining
a reproducible probability-based selection within each stratum. Quarterly rows do not increase the
number of independent issuers; the final model evaluation therefore continues to report
issuer-clustered uncertainty.
