# Phase 1 Feature and KPI Dictionary

## Forecast KPIs

| KPI | Formula | Dimension | Important handling |
|---|---|---|---|
| Interest coverage | TTM operating income / TTM interest expense | Debt-service capacity | Preserve negative operating income; reject zero/immaterial denominators |
| Free-cash-flow margin | (TTM operating cash flow − TTM capital expenditures) / TTM revenue | Liquidity generation | Normalize capital-expenditure sign and guard zero revenue |
| Total debt/assets | (short-term debt + long-term debt) / total assets | Capital structure | Missing debt components require a documented zero-versus-missing rule |

Net-debt/EBITDA is a secondary diagnostic only and is valid only when EBITDA is positive and not
near zero.

## Feature families

- Current levels and trailing-four-quarter values.
- Quarter-over-quarter and year-over-year changes.
- Rolling volatility and trend.
- Missingness and reporting-quality indicators.
- Sector and industry medians, percentiles, and distance-to-peer values.
- Point-in-time macro levels and changes.
- Forecast means, changes, lower bounds, and interval widths.

Every implemented feature must add its precise source columns, availability rule, transformation,
missingness policy, outlier policy, and economic rationale to this document or a generated data
dictionary.
