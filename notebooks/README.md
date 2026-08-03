# Notebook policy

Use numbered notebooks for investigation and communication. Reusable acquisition, fiscal
normalization, point-in-time joins, features, labels, model fitting, and evaluation logic must be
moved into `src/cfd` and tested before results are treated as reproducible.

Planned sequence:

1. Universe audit.
2. Financial data and XBRL mapping audit.
3. Candidate-label feasibility.
4. Financial and sector EDA.
5. Forecast baseline and state-space comparison.
6. Time-aware classification and model selection.
