.DEFAULT_GOAL := help
PYTHON ?= python3

.PHONY: help bootstrap install lock test lint format typecheck defs-check check dagster config-check clean reproduce-phase1 dashboard release-audit

help:
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z_-]+:.*## / {printf "%-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

bootstrap: ## Create .venv with standard Python tooling
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install --upgrade pip uv
	.venv/bin/uv sync --extra dev

install: ## Install locked dependencies with uv
	.venv/bin/uv sync --extra dev

lock: ## Refresh uv.lock after changing pyproject.toml
	.venv/bin/uv lock

test: ## Run unit and integration tests excluding network tests
	.venv/bin/pytest -m "not network"

lint: ## Check formatting and lint rules
	.venv/bin/ruff format --check .
	.venv/bin/ruff check .

format: ## Apply formatting and safe lint fixes
	.venv/bin/ruff format .
	.venv/bin/ruff check --fix .

typecheck: ## Run strict static type checks
	.venv/bin/mypy src

defs-check: ## Validate that Dagster can load the complete asset graph
	.venv/bin/dagster definitions validate -m cfd.orchestration.definitions

check: config-check lint typecheck defs-check test ## Run the local quality gate

config-check: ## Validate project configuration and create required local directories
	.venv/bin/cfd validate-config

dagster: ## Start the local Dagster UI
	.venv/bin/dagster dev -m cfd.orchestration.definitions

dashboard: ## Rebuild and reconcile the four Tableau delivery extracts
	.venv/bin/python -m cfd.cli run-stages-17-18

release-audit: ## Run the Phase 1 publication audit
	.venv/bin/python -c "from cfd.stage18 import run_stage_18; print(run_stage_18())"

reproduce-phase1: check ## Rebuild Phase 1 from the certified local public-data cache
	.venv/bin/python -m cfd.cli run-stages-8-12
	.venv/bin/python -m cfd.cli run-stages-13-16
	.venv/bin/python -m cfd.cli run-stages-17-18

clean: ## Remove generated caches (preserves source data)
	find . -type d -name __pycache__ -prune -exec rm -r {} +
	find . -type d -name .pytest_cache -prune -exec rm -r {} +
	find . -type d -name .ruff_cache -prune -exec rm -r {} +
