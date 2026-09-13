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
    "config.algo",
    "config.world",
    "engine.core.road_network",
    "engine.core.city_layout",
    "engine.schematic.road",
    "engine.schematic.building",
    "engine.world.anvil_world_reader",
    "engine.world.writer",
)

ORDERED_STAGE_SPECS = (
    StageSpec("roads", "pipeline.01_roads.stage"),
    StageSpec("builds", "pipeline.02_builds.stage"),
    StageSpec("preview", "pipeline.03_preview.stage"),
    StageSpec("city", "pipeline.04_city.stage"),
    StageSpec("world", "pipeline.05_world.stage"),
)

PIPELINE_INTERNAL_MODULES = (
    "pipeline.01_roads.extract",
    "pipeline.01_roads.render",
    "pipeline.02_builds.extract",
    "pipeline.02_builds.render",
    "pipeline.03_preview.roads",
    "pipeline.03_preview.builds",
    "pipeline.03_preview.grid",
    "pipeline.03_preview.city",
    "pipeline.04_city.construct",
    "pipeline.04_city.render",
    "pipeline.05_world.export",
)

STAGES = {spec.key: spec for spec in ORDERED_STAGE_SPECS}
PIPELINE_STAGE_MODULES = tuple(spec.module for spec in ORDERED_STAGE_SPECS)
RELOAD_ORDER = (*PIPELINE_DEPENDENCY_MODULES, *PIPELINE_INTERNAL_MODULES, *PIPELINE_STAGE_MODULES)


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
