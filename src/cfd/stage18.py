"""Stage 18 reproducibility and public-release audit."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pandas as pd

from cfd.config import repository_root
from cfd.stage17 import run_stage_17


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_phase1_release() -> pd.DataFrame:
    root = repository_root()
    exports = root / "dashboards" / "tableau" / "exports"
    checks: list[dict[str, Any]] = []

    def add(category: str, check: str, passed: bool, evidence: Any) -> None:
        checks.append(
            {
                "category": category,
                "check": check,
                "passed": bool(passed),
                "evidence": str(evidence),
            }
        )

    required_exports = [
        "portfolio_overview.csv",
        "company_watchlist.csv",
        "company_detail_history.csv",
        "model_performance.csv",
    ]
    for filename in required_exports:
        path = exports / filename
        add("dashboard", f"{filename}_exists", path.is_file(), path.relative_to(root))
        if path.is_file():
            add(
                "dashboard",
                f"{filename}_nonempty",
                len(pd.read_csv(path)) > 0,
                len(pd.read_csv(path)),
            )
    reconciliation = pd.read_csv(root / "reports" / "generated" / "tableau_reconciliation.csv")
    add(
        "dashboard",
        "tableau_reconciliation",
        bool(reconciliation["passed"].all()),
        len(reconciliation),
    )

    workbook = root / "dashboards" / "tableau" / "Corporate_Financial_Deterioration.twb"
    try:
        ElementTree.parse(workbook)
        workbook_valid = True
    except (ElementTree.ParseError, FileNotFoundError):
        workbook_valid = False
    add("dashboard", "tableau_workbook_valid_xml", workbook_valid, workbook.relative_to(root))
    if workbook_valid:
        tree = ElementTree.parse(workbook)
        dashboard_names = {
            element.attrib.get("name", "") for element in tree.findall("./dashboards/dashboard")
        }
        expected_dashboards = {
            "Portfolio Overview",
            "Analyst Watchlist",
            "Company Detail",
            "Model Performance",
        }
        add(
            "dashboard",
            "four_tableau_pages_defined",
            dashboard_names == expected_dashboards,
            sorted(dashboard_names),
        )
        connections = tree.findall(".//connection[@class='textscan']")
        add(
            "dashboard",
            "tableau_connections_are_relative",
            bool(connections)
            and all(
                not Path(item.attrib.get("directory", "")).is_absolute() for item in connections
            ),
            [item.attrib.get("directory", "") for item in connections],
        )

    package = root / "dashboards" / "tableau" / "Corporate_Financial_Deterioration.twbx"
    expected_package_files = {f"Data/{filename}" for filename in required_exports}
    try:
        with zipfile.ZipFile(package) as archive:
            package_files = set(archive.namelist())
            embedded_workbook_name = next(name for name in package_files if name.endswith(".twb"))
            embedded_workbook = archive.read(embedded_workbook_name).decode("utf-8")
        package_valid = expected_package_files.issubset(package_files)
        package_private = "/Users/" not in embedded_workbook
    except (zipfile.BadZipFile, FileNotFoundError, StopIteration, UnicodeDecodeError):
        package_valid = False
        package_private = False
    add(
        "dashboard",
        "tableau_package_contains_four_extracts",
        package_valid,
        package.relative_to(root),
    )
    add(
        "privacy", "tableau_package_has_no_machine_path", package_private, package.relative_to(root)
    )

    required_docs = [
        "README.md",
        "docs/data_card.md",
        "docs/model_card.md",
        "docs/architecture.md",
        "docs/assumptions_and_limitations.md",
        "docs/reproducibility.md",
        "docs/case_study.md",
        "docs/resume_summary.md",
        "docs/stages_17_18_execution.md",
    ]
    for filename in required_docs:
        path = root / filename
        add("documentation", f"{filename}_exists", path.is_file(), filename)
        if path.is_file():
            add(
                "documentation",
                f"{filename}_substantive",
                path.stat().st_size >= 500,
                path.stat().st_size,
            )

    manifest_files = list((root / "data" / "manifests").glob("*.manifest.json"))
    add("lineage", "source_manifests_present", len(manifest_files) >= 66, len(manifest_files))
    add("environment", "dependency_lock_present", (root / "uv.lock").is_file(), "uv.lock")
    add(
        "environment",
        "environment_template_present",
        (root / ".env.example").is_file(),
        ".env.example",
    )
    add(
        "model",
        "champion_artifact_present",
        (root / "artifacts" / "champion_classifier.joblib").is_file(),
        "artifacts/champion_classifier.joblib",
    )
    add(
        "model",
        "holdout_metrics_present",
        (root / "reports" / "generated" / "final_holdout_metrics.csv").is_file(),
        "final_holdout_metrics.csv",
    )

    publication_files = [root / filename for filename in required_docs]
    publication_files += [root / "dashboards" / "tableau" / "README.md", workbook]
    secret_pattern = re.compile(
        r"""(?ix)(
            fred_api_key\s*=\s*["']?[a-f0-9]{20,}
            | api[_-]?key\s*=\s*["']?[^<\s"']{12,}
            | password\s*=\s*["'][^"']+["']
        )"""
    )
    local_path_pattern = re.compile(r"/Users/[^/\s]+/")
    findings: list[str] = []
    for path in publication_files:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if secret_pattern.search(text) or local_path_pattern.search(text):
            findings.append(str(path.relative_to(root)))
    add("privacy", "no_credentials_or_machine_paths", not findings, findings or "none")

    frame = pd.DataFrame(checks)
    if not frame["passed"].all():
        failures = frame.loc[~frame["passed"]].to_dict("records")
        raise ValueError(f"Stage 18 release audit failed: {failures}")
    return frame


def run_stage_18() -> dict[str, Any]:
    root = repository_root()
    reports = root / "reports" / "generated"
    checks = validate_phase1_release()
    checks.to_csv(reports / "stage18_release_checks.csv", index=False)
    release_files = [
        root / "configs" / "project.yml",
        root / "configs" / "selected_universe.yml",
        root / "configs" / "label.yml",
        root / "configs" / "modeling.yml",
        root / "configs" / "tableau.yml",
        root / "reports" / "generated" / "champion_selection_frozen.json",
        root / "dashboards" / "tableau" / "Corporate_Financial_Deterioration.twb",
        root / "dashboards" / "tableau" / "Corporate_Financial_Deterioration.twbx",
    ]
    payload = {
        "status": "complete",
        "stage": 18,
        "release": "Phase 1 minimum credible product",
        "release_version": "1.0.0-phase1",
        "checks_passed": int(checks["passed"].sum()),
        "checks_failed": int((~checks["passed"]).sum()),
        "artifact_sha256": {
            str(path.relative_to(root)): _sha256(path) for path in release_files if path.is_file()
        },
        "reproduction_command": "make reproduce-phase1",
        "network_required_for_cached_rebuild": False,
        "publication_data_policy": "free public SEC and FRED data only",
    }
    (reports / "stage18_summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def run_stages_17_to_18() -> dict[str, Any]:
    return {"stage_17": run_stage_17(), "stage_18": run_stage_18()}
