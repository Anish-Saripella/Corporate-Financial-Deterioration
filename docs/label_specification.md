# Candidate Deterioration Label

A positive candidate event occurs when the minimum TTM interest coverage observed during the
next four fiscal quarters is below 1.5 **and** represents at least a 40% decline from coverage at
the decision date.

The configuration is intentionally marked `candidate_pending_training_period_event_audit`. It
cannot be finalized until development-period analysis establishes:

- Positive rows and distinct company episodes.
- Prevalence by sector, company size, year, and economic environment.
- Treatment of already-distressed issuers and negative operating income.
- Effects of zero, small, missing, or differently reported interest expense.
- A defensible episode-collapse rule for overlapping four-quarter windows.
- Enough distinct final-holdout episodes for meaningful evaluation.

Thresholds may be adjusted only using the development period and must be frozen before final
model evaluation. The label represents deterioration in debt-service capacity—not default,
bankruptcy, or a credit rating.
