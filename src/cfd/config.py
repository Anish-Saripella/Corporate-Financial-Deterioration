"""Typed project configuration and path management."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base model that rejects misspelled or undocumented configuration keys."""

    model_config = ConfigDict(extra="forbid")


class ProjectMetadata(StrictModel):
    name: str
    version: str
    timezone: str
    random_seed: int


class Scope(StrictModel):
    start_date: date
    end_date: date
    prediction_horizon_fiscal_quarters: int = Field(gt=0)
    final_company_count: int = Field(gt=0)
    candidate_company_count_min: int = Field(gt=0)
    candidate_company_count_max: int = Field(gt=0)
    sectors: list[str]
    forecast_kpis: list[str]
    primary_outcome: str

    @model_validator(mode="after")
    def validate_scope(self) -> Scope:
        if len(self.sectors) != 2:
            raise ValueError("Phase 1 must contain exactly two sectors")
        if len(self.forecast_kpis) != 3:
            raise ValueError("Phase 1 must contain exactly three forecast KPIs")
        if self.candidate_company_count_min > self.candidate_company_count_max:
            raise ValueError("candidate company bounds are reversed")
        if self.final_company_count > self.candidate_company_count_min:
            raise ValueError("final universe must not exceed candidate-universe minimum")
        return self


class Storage(StrictModel):
    data_dir: str
    raw_dir: str
    interim_dir: str
    processed_dir: str
    manifests_dir: str
    duckdb_path: str
    tableau_export_dir: str


class SourcePolicy(StrictModel):
    free_public_only: bool
    allowed_sources: list[str]
    market_data_phase1: bool
    raw_data_committed_to_git: bool


class Validation(StrictModel):
    strategy: str
    minimum_training_quarters: int = Field(gt=0)
    forecast_horizons: list[int]
    preliminary_holdout_start: date
    final_holdout_requires_event_audit: bool
    random_train_test_split_allowed: bool


class ProjectConfig(StrictModel):
    project: ProjectMetadata
    scope: Scope
    storage: Storage
    source_policy: SourcePolicy
    validation: Validation


def repository_root() -> Path:
    """Return the repository root independent of the current working directory."""

    return Path(__file__).resolve().parents[2]


def read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML mapping and reject empty/non-mapping documents."""

    with path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return payload


def load_project_config(path: Path | None = None) -> ProjectConfig:
    """Load and validate the central project configuration."""

    config_path = path or repository_root() / "configs" / "project.yml"
    return ProjectConfig.model_validate(read_yaml(config_path))


def resolve_storage_paths(config: ProjectConfig) -> dict[str, Path]:
    """Resolve configured storage paths, honoring documented environment overrides."""

    root = repository_root()
    data_override = os.getenv("CFD_DATA_DIR")
    duckdb_override = os.getenv("CFD_DUCKDB_PATH")
    data_root = Path(data_override) if data_override else root / config.storage.data_dir
    if not data_root.is_absolute():
        data_root = root / data_root

    def under_data(configured: str) -> Path:
        if data_override:
            return data_root / Path(configured).name
        value = Path(configured)
        return value if value.is_absolute() else root / value

    duckdb_path = Path(duckdb_override) if duckdb_override else root / config.storage.duckdb_path
    if not duckdb_path.is_absolute():
        duckdb_path = root / duckdb_path

    return {
        "data": data_root,
        "raw": under_data(config.storage.raw_dir),
        "interim": under_data(config.storage.interim_dir),
        "processed": under_data(config.storage.processed_dir),
        "manifests": under_data(config.storage.manifests_dir),
        "duckdb": duckdb_path,
        "tableau": root / config.storage.tableau_export_dir,
    }


def ensure_local_directories(config: ProjectConfig) -> dict[str, Path]:
    """Create only the narrow, configured local directories required by the project."""

    paths = resolve_storage_paths(config)
    for key, path in paths.items():
        target = path.parent if key == "duckdb" else path
        target.mkdir(parents=True, exist_ok=True)
    return paths
