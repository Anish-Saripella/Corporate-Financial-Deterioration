# Assumptions and Limitations

## Scope assumptions

Phase 1 deliberately uses two contrasting sectors: cyclical Consumer Discretionary and regulated,
more defensive Utilities. It fixes 30 currently listed companies per sector and excludes delisted
firms. This keeps public-data engineering and manual validation feasible, but creates survivorship
bias and prevents claims about the full corporate-credit population. The synthetic portfolio is a
research watchlist, not a bank loan book; exposure, recovery, covenant, collateral, and private
borrower information are unavailable.

Fiscal quarters are standardized as issuer FQ1-FQ4 for modeling, while actual period ends and
filing dates remain in the data. Different fiscal calendars therefore become comparable without
pretending their economic exposure dates are identical. SEC filing dates proxy when facts become
known. Macro series use historical vintages where supported and documented release-date proxies
otherwise.

## Outcome and forecast assumptions

Deterioration requires both interest coverage below 1.5x in the next four quarters and at least a
40% relative decline. This is an interpretable debt-service warning condition, not default,
bankruptcy, or loss probability. Adjacent quarterly labels overlap and must not be treated as
independent events. Negative operating income is retained; zero or immaterial interest denominators
are rejected rather than producing misleading coverage ratios.

State-space models assume that relatively simple latent trends and optional macro regressors can
summarize KPI dynamics. Forecast intervals materially under-cover for some four-quarter targets,
so uncertainty is diagnostic rather than a guaranteed confidence statement. Random walks remain
the mandatory benchmark; added complexity must win out of time to be credible.

## Classifier and dashboard limitations

The champion is a gradient-boosted tree ensemble trained on only 60 firms and two sectors. OOF and
holdout performance show useful ranking lift, but precision is modest, particularly for Utilities.
Feature importance is associational and not causal. The alert threshold is a research threshold,
not an approved credit policy, and the 2023+ holdout is not retuned after evaluation.

The Power BI watchlist shows the latest evaluated prediction for each company, which may have a
different filing decision date across issuers. It does not invent scores for unavailable future
labels or display in-sample fitted probabilities. Dashboard data may become stale after new filings;
the displayed freshness date and source manifests should be checked before interpretation.

The delivered PBIX is a valid package with an embedded data model, four named pages, and headline
KPIs that reconcile to the certified import workbook. The supplied authoring-canvas screenshots
also expose several unbound placeholder visuals. Until those bindings receive a final Power BI
Desktop pass and refreshed screenshots, the report is analytically auditable but not fully
presentation-ready.

## Appropriate interpretation

Use the platform to prioritize analyst review, compare sector patterns, examine KPI trajectories,
and demonstrate point-in-time data science. Do not use it to approve credit, set limits, trade
securities, estimate regulatory capital, or make claims about an individual company's solvency.
