# Reproducibility Standard

## Environment

- Python is constrained to 3.12.
- `pyproject.toml` declares direct dependencies.
- `uv.lock` records a cross-platform dependency resolution.
- `.env.example` documents required secrets without exposing them.

## Data

- Raw responses are immutable by default and excluded from Git.
- Each acquisition produces a JSON manifest containing source, URL, non-secret parameters,
  retrieval time, output path, byte count, and SHA-256 checksum.
- Transformations are implemented in `src/cfd` or versioned SQL, never only in notebooks.
- Company exclusions and XBRL overrides are stored as data/configuration, not undocumented code.

## Modeling

- Random seeds and configurations are versioned.
- Fold boundaries, fitted preprocessing, features, metrics, and artifacts are logged.
- Final metrics derive from out-of-fold or final forward predictions.
- Published development probabilities and metrics are out of fold; the final holdout is labeled
  separately and unscored training/history rows remain unscored.

## Public repository checklist

- No `.env`, API keys, credentials, local absolute paths, or proprietary data.
- README includes exact setup and reproduction commands.
- License and source attribution are present.
- CI runs configuration validation, linting, and non-network tests.
- A data card and model card are completed before results are published.
