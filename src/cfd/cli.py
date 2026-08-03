"""Small, stable command-line interface for reproducible local workflows."""

from __future__ import annotations

import argparse
import json

from cfd.config import ensure_local_directories, load_project_config, read_yaml, repository_root
from cfd.database import initialize_database


def validate_configuration() -> dict[str, object]:
    config = load_project_config()
    root = repository_root()
    for filename in [
        "universe.yml",
        "label.yml",
        "macro_series.yml",
        "sec_tags.yml",
        "tableau.yml",
    ]:
        read_yaml(root / "configs" / filename)
    paths = ensure_local_directories(config)
    database_path = initialize_database(config)
    return {
        "status": "ok",
        "project": config.project.name,
        "sectors": config.scope.sectors,
        "forecast_kpis": config.scope.forecast_kpis,
        "database": str(database_path),
        "directories": {key: str(path) for key, path in paths.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="cfd")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate-config", help="Validate configs and initialize local storage")
    subparsers.add_parser("show-scope", help="Print the confirmed Phase 1 scope")
    arguments = parser.parse_args()

    if arguments.command == "validate-config":
        print(json.dumps(validate_configuration(), indent=2))
    elif arguments.command == "show-scope":
        print(load_project_config().scope.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
