from pathlib import Path

import pytest
import yaml

from cfd.config import ProjectConfig, load_project_config, resolve_storage_paths


def test_confirmed_phase1_scope_is_locked() -> None:
    config = load_project_config()
    assert config.scope.sectors == ["Consumer Discretionary", "Utilities"]
    assert config.scope.forecast_kpis == [
        "interest_coverage",
        "free_cash_flow_margin",
        "total_debt_to_assets",
    ]
    assert config.source_policy.free_public_only is True
    assert config.source_policy.market_data_phase1 is False
    assert config.validation.random_train_test_split_allowed is False


def test_scope_rejects_extra_sector() -> None:
    path = Path("configs/project.yml")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    payload["scope"]["sectors"].append("Industrials")
    with pytest.raises(ValueError, match="exactly two sectors"):
        ProjectConfig.model_validate(payload)


def test_storage_paths_are_inside_repository_by_default() -> None:
    paths = resolve_storage_paths(load_project_config())
    repository = Path(__file__).resolve().parents[2]
    assert all(path == repository or repository in path.parents for path in paths.values())
