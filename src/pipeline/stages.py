"""Central registry of pipeline stage modules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StageSpec:
    key: str
    module: str


PIPELINE_DEPENDENCY_MODULES = (
    "config.config_algo",
    "config.config_world",
    "engine.road_network",
    "engine.city_layout",
    "engine.road_schematic",
    "engine.building_schematic",
    "engine.anvil_world_reader",
)

ORDERED_STAGE_SPECS = (
    StageSpec("roads_simulation", "pipeline.01_roads_simulation"),
    StageSpec("roads_extract", "pipeline.01_roads_extract"),
    StageSpec("roads_render", "pipeline.01_roads_render"),
    StageSpec("builds_simulation", "pipeline.02_builds_simulation"),
    StageSpec("builds_extract", "pipeline.02_builds_extract"),
    StageSpec("builds_render", "pipeline.02_builds_render"),
    StageSpec("grid_simulation", "pipeline.03_grid_simulation"),
    StageSpec("grid_construct", "pipeline.03_grid_construct"),
    StageSpec("grid_render", "pipeline.03_grid_render"),
    StageSpec("city_simulation", "pipeline.04_city_simulation"),
    StageSpec("city_construct", "pipeline.04_city_construct"),
    StageSpec("city_render", "pipeline.04_city_render"),
)

STAGES = {spec.key: spec for spec in ORDERED_STAGE_SPECS}
PIPELINE_STAGE_MODULES = tuple(spec.module for spec in ORDERED_STAGE_SPECS)
RELOAD_ORDER = (*PIPELINE_DEPENDENCY_MODULES, *PIPELINE_STAGE_MODULES)


def stage_module(stage_key: str) -> str:
    try:
        return STAGES[stage_key].module
    except KeyError as exc:
        raise KeyError(f"Unknown pipeline stage: {stage_key}") from exc
