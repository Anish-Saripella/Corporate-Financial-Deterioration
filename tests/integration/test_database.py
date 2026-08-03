from pathlib import Path

import duckdb

from cfd.config import load_project_config
from cfd.database import initialize_database


def test_database_schema_initialization(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "test.duckdb"
    monkeypatch.setenv("CFD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CFD_DUCKDB_PATH", str(database_path))
    assert initialize_database(load_project_config()) == database_path
    with duckdb.connect(str(database_path), read_only=True) as connection:
        tables = connection.execute(
            "SELECT table_schema, table_name FROM information_schema.tables"
        ).fetchall()
    assert ("metadata", "pipeline_runs") in tables
    assert ("metadata", "universe_decisions") in tables
