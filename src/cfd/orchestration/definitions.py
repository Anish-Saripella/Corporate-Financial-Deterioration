"""Dagster code location."""

from dagster import Definitions, load_assets_from_modules

from cfd.orchestration import assets

defs = Definitions(assets=load_assets_from_modules([assets]))
