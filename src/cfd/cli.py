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
        "analytical_panel.yml",
        "feature_registry.yml",
        "temporal_validation.yml",
        "plot_style.yml",
        "modeling.yml",
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
    stages_parser = subparsers.add_parser(
        "run-stages-0-7", help="Execute and audit Phase 1 Stages 0 through 7"
    )
    stages_parser.add_argument(
        "--refresh-universe",
        action="store_true",
        help="Explicitly allow candidate-history downloads after the final store is materialized",
    )
    subparsers.add_parser(
        "verify-source-manifests", help="Verify checksums for all cached source artifacts"
    )
    subparsers.add_parser(
        "materialize-final-store",
        help="Retain local company financial data only for the frozen selected universe",
    )
    subparsers.add_parser(
        "run-stages-8-12",
        help="Certify the panel, label, EDA, features, and temporal validation artifacts",
    )
    modeling_parser = subparsers.add_parser(
        "run-stages-13-16",
        help="Forecast KPIs, train/select models, and validate production artifacts",
    )
    modeling_parser.add_argument(
        "--reuse-forecasts",
        action="store_true",
        help="Run a smaller model refresh using the existing certified Stage 13 forecasts",
    )
    subparsers.add_parser(
        "run-stages-17-18",
        help="Build Tableau delivery artifacts and audit the Phase 1 release",
    )
    arguments = parser.parse_args()

    if arguments.command == "validate-config":
        print(json.dumps(validate_configuration(), indent=2))
    elif arguments.command == "show-scope":
        print(load_project_config().scope.model_dump_json(indent=2))
    elif arguments.command == "run-stages-0-7":
        from cfd.stages import run_stages_0_to_7

        print(
            json.dumps(
                run_stages_0_to_7(refresh_universe=arguments.refresh_universe),
                indent=2,
                default=str,
            )
        )
    elif arguments.command == "verify-source-manifests":
        from cfd.stages import verify_source_manifests

        print(json.dumps(verify_source_manifests(), indent=2, default=str))
    elif arguments.command == "materialize-final-store":
        from cfd.local_store import materialize_final_universe_store

        print(json.dumps(materialize_final_universe_store(), indent=2, default=str))
    elif arguments.command == "run-stages-8-12":
        from cfd.stages_8_12 import run_stages_8_to_12

        print(json.dumps(run_stages_8_to_12(), indent=2, default=str))
    elif arguments.command == "run-stages-13-16":
        from cfd.stage16 import run_stages_13_to_16

        print(
            json.dumps(
                run_stages_13_to_16(reuse_forecasts=arguments.reuse_forecasts),
                indent=2,
                default=str,
            )
        )
    elif arguments.command == "run-stages-17-18":
        from cfd.stage18 import run_stages_17_to_18

        print(json.dumps(run_stages_17_to_18(), indent=2, default=str))


if __name__ == "__main__":
    main()
