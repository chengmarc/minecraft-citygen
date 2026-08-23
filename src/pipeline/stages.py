"""Central registry of pipeline stage modules, plus the shared stage runner.

Every numbered stage exposes ``run(*, logger=None, progress=None, ...)``. Two
helpers here remove the boilerplate that used to be copy-pasted into each stage:

- :func:`noop` is the default logger/progress callback, so a stage body can call
  ``logger(...)``/``progress(...)`` unconditionally instead of guarding every
  call with ``if logger is not None``.
- :func:`run_stage_cli` turns a stage's ``run`` into a command-line entry point,
  reading each option's default from ``run``'s own signature so the CLI and the
  in-process callers stay in sync.
"""

from __future__ import annotations

import argparse
import inspect
from dataclasses import dataclass


@dataclass(frozen=True)
class StageSpec:
    key: str
    module: str


PIPELINE_DEPENDENCY_MODULES = (
    "config.config_algo",
    "config.config_world",
    "engine.core.road_network",
    "engine.core.city_layout",
    "engine.schematic.road",
    "engine.schematic.building",
    "engine.world.anvil_world_reader",
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


def noop(*args, **kwargs) -> None:
    """A logger/progress callback that discards its arguments."""


# CLI option specs shared by the stage runners. Defaults are pulled from each
# stage's own ``run`` signature, so only the arg *type*/action and help live here.
# Keys match ``run`` keyword names; underscores map to hyphenated CLI flags.
_STAGE_CLI_ARGS = {
    "seed": {"type": int, "help": "generation seed"},
    "fine": {"type": int, "help": "fine grid edge in cells (even)"},
    "preview": {"type": int, "help": "edge of preview png (0 = full res)"},
    "out": {"type": str, "help": "output path (default: derived from seed)"},
    "key": {"type": str, "help": "render one catalog key, e.g. 001"},
    "no_ground_fill": {
        "action": "store_true",
        "help": "leave empty non-road lot cells as air instead of filling them",
    },
}


def run_stage_cli(run, *params: str, logger=print):
    """Run a stage's ``run`` as a command-line script.

    ``params`` names the options to expose (keys of :data:`_STAGE_CLI_ARGS`);
    each option's default is taken from ``run``'s own signature so there is a
    single source of truth. ``run`` is always invoked with ``logger`` (default:
    :func:`print`).
    """
    signature = inspect.signature(run)
    parser = argparse.ArgumentParser()
    for name in params:
        parser.add_argument(
            f"--{name.replace('_', '-')}",
            default=signature.parameters[name].default,
            **_STAGE_CLI_ARGS[name],
        )
    return run(logger=logger, **vars(parser.parse_args()))
