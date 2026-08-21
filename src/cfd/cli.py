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
        "analytical_panel.yml",
        "feature_registry.yml",
        "temporal_validation.yml",
        "plot_style.yml",
        "modeling.yml",
        "phase2.yml",
        "phase3.yml",
        "phase3_reporting.yml",
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
    phase2_readiness = subparsers.add_parser(
        "audit-phase2-readiness",
        help="Audit whether the real expanded panel can support Phase 2 claims",
    )
    phase2_readiness.add_argument(
        "--panel",
        default=None,
        help="Optional path to a real Phase 2 panel parquet file",
    )
    phase2_universe = subparsers.add_parser(
        "freeze-phase2-universe",
        help="Select the configured eligible active-company target per sector and freeze reserves",
    )
    phase2_universe.add_argument(
        "--eligibility-audit",
        default=None,
        help="Optional path to the real all-candidate eligibility parquet file",
    )
    subparsers.add_parser(
        "build-phase2-eligibility",
        help="Ingest and audit every mapped active SEC candidate before sampling",
    )
    phase2_analysis = subparsers.add_parser(
        "analyze-phase2-development",
        help="Build workload, episode, calibration, and uncertainty evidence from real OOF scores",
    )
    phase2_analysis.add_argument(
        "--predictions",
        default=None,
        help="Optional path to real Phase 2 out-of-fold predictions",
    )
    subparsers.add_parser(
        "build-phase2-panel",
        help="Certify selected/reserve issuers and materialize the final point-in-time panel",
    )
    subparsers.add_parser(
        "run-phase2-development-models",
        help="Run feature ablations and nested temporal Phase 2 logistic challengers",
    )
    subparsers.add_parser(
        "run-phase2-forecasts",
        help="Backtest KPI forecasts, recalibrate intervals, and build optional forecast features",
    )
    subparsers.add_parser(
        "build-phase2-governance",
        help="Build company explanations, monitoring evidence, and Phase 2 model/data cards",
    )
    subparsers.add_parser(
        "write-phase2-research-report",
        help="Write the accessible Phase 2 development research report from generated evidence",
    )
    subparsers.add_parser(
        "run-phase2-horizon-sensitivity",
        help="Compare two- and four-quarter deterioration horizons on paired temporal folds",
    )
    subparsers.add_parser(
        "run-phase3-development",
        help="Compare Phase 3 models and ensembles on rolling out-of-fold windows",
    )
    subparsers.add_parser(
        "evaluate-phase3-final-test",
        help="Evaluate the frozen Phase 3 champion on the sealed late-2024 cohort once",
    )
    subparsers.add_parser(
        "build-phase3-evidence",
        help="Build uncertainty intervals and the Phase 3 evidence summary",
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
    elif arguments.command == "audit-phase2-readiness":
        from pathlib import Path

        from cfd.stage19 import run_stage_19

        panel = Path(arguments.panel) if arguments.panel else None
        print(json.dumps(run_stage_19(panel), indent=2, default=str))
    elif arguments.command == "freeze-phase2-universe":
        from pathlib import Path

        from cfd.stage20 import run_stage_20

        audit = Path(arguments.eligibility_audit) if arguments.eligibility_audit else None
        print(json.dumps(run_stage_20(audit), indent=2, default=str))
    elif arguments.command == "build-phase2-eligibility":
        from cfd.stage21 import run_stage_21

        print(json.dumps(run_stage_21(), indent=2, default=str))
    elif arguments.command == "analyze-phase2-development":
        from pathlib import Path

        from cfd.stage22 import run_stage_22

        predictions = Path(arguments.predictions) if arguments.predictions else None
        print(json.dumps(run_stage_22(predictions), indent=2, default=str))
    elif arguments.command == "build-phase2-panel":
        from cfd.stage24 import run_stage_24

        print(json.dumps(run_stage_24(), indent=2, default=str))
    elif arguments.command == "run-phase2-development-models":
        from cfd.stage23 import run_stage_23

        print(json.dumps(run_stage_23(), indent=2, default=str))
    elif arguments.command == "run-phase2-forecasts":
        from cfd.stage25 import run_stage_25

        print(json.dumps(run_stage_25(), indent=2, default=str))
    elif arguments.command == "build-phase2-governance":
        from cfd.stage26 import run_stage_26

        print(json.dumps(run_stage_26(), indent=2, default=str))
    elif arguments.command == "write-phase2-research-report":
        from cfd.stage27 import run_stage_27

        print(json.dumps(run_stage_27(), indent=2, default=str))
    elif arguments.command == "run-phase2-horizon-sensitivity":
        from cfd.stage28 import run_stage_28

        print(json.dumps(run_stage_28(), indent=2, default=str))
    elif arguments.command == "run-phase3-development":
        from cfd.stage29 import run_stage_29

        print(json.dumps(run_stage_29(), indent=2, default=str))
    elif arguments.command == "evaluate-phase3-final-test":
        from cfd.stage30 import run_stage_30

        print(json.dumps(run_stage_30(), indent=2, default=str))
    elif arguments.command == "build-phase3-evidence":
        from cfd.stage31 import run_stage_31

        print(json.dumps(run_stage_31(), indent=2, default=str))


if __name__ == "__main__":
    main()
