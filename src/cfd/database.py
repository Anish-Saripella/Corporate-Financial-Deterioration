"""DuckDB initialization and versioned SQL application."""

from __future__ import annotations

from pathlib import Path

import duckdb

from cfd.config import ProjectConfig, ensure_local_directories, repository_root


def initialize_database(config: ProjectConfig) -> Path:
    """Create the local database and apply idempotent schema SQL."""

    paths = ensure_local_directories(config)
    database_path = paths["duckdb"]
    schema_path = repository_root() / "sql" / "staging" / "001_source_schemas.sql"
    with duckdb.connect(str(database_path)) as connection:
        connection.execute(schema_path.read_text(encoding="utf-8"))
    return database_path
