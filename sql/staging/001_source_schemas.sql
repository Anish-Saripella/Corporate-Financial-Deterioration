CREATE SCHEMA IF NOT EXISTS metadata;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS marts;

CREATE TABLE IF NOT EXISTS metadata.pipeline_runs (
    run_id VARCHAR PRIMARY KEY,
    started_at_utc TIMESTAMP NOT NULL,
    completed_at_utc TIMESTAMP,
    status VARCHAR NOT NULL,
    git_commit VARCHAR,
    config_version VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS metadata.source_manifests (
    source VARCHAR NOT NULL,
    source_url VARCHAR NOT NULL,
    retrieved_at_utc TIMESTAMP NOT NULL,
    output_path VARCHAR NOT NULL,
    sha256 VARCHAR NOT NULL,
    byte_count BIGINT NOT NULL,
    parameters_json JSON NOT NULL,
    PRIMARY KEY (source, sha256)
);

CREATE TABLE IF NOT EXISTS metadata.universe_decisions (
    selection_as_of DATE NOT NULL,
    cik VARCHAR NOT NULL,
    ticker VARCHAR,
    company_name VARCHAR NOT NULL,
    sector VARCHAR,
    industry VARCHAR,
    included BOOLEAN NOT NULL,
    reason_code VARCHAR NOT NULL,
    evidence_json JSON,
    PRIMARY KEY (selection_as_of, cik)
);
