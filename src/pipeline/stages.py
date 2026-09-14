"""Central registry of pipeline stages, plus shared stage runners.

Every numbered stage is orchestrated here. Two helpers remove the boilerplate
that used to be copy-pasted into stage wrappers:

- :func:`noop` is the default logger/progress callback, so a stage body can call
  ``logger(...)``/``progress(...)`` unconditionally instead of guarding every
  call with ``if logger is not None``.
- :func:`run_stage_cli` turns a stage's ``run`` into a command-line entry point,
  reading each option's default from ``run``'s own signature so the CLI and the
  in-process callers stay in sync.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.algo import DEFAULT_SEED, FINE as DEFAULT_FINE


@dataclass(frozen=True)
class StageSpec:
    key: str
    runner: str


ROADS_EXTRACT = "pipeline.01_roads.extract"
ROADS_RENDER = "pipeline.01_roads.render"
BUILDS_EXTRACT = "pipeline.02_builds.extract"
BUILDS_RENDER = "pipeline.02_builds.render"
PREVIEW_ROADS = "pipeline.03_preview.roads"
PREVIEW_BUILDS = "pipeline.03_preview.builds"
PREVIEW_GRID = "pipeline.03_preview.grid"
PREVIEW_CITY = "pipeline.03_preview.city"
CITY_CONSTRUCT = "pipeline.04_city.construct"
CITY_RENDER = "pipeline.04_city.render"
WORLD_EXPORT = "pipeline.05_world.export"


PIPELINE_DEPENDENCY_MODULES = (
    "config.path",
    "config.algo",
    "config.world",
    "config.render",
    "engine.core.road_network",
    "engine.core.city_layout",
    "engine.schematic.road",
    "engine.schematic.building",
    "engine.world.anvil_world_reader",
    "engine.world.writer",
)

ORDERED_STAGE_SPECS = (
    StageSpec("roads", "run_roads"),
    StageSpec("builds", "run_builds"),
    StageSpec("preview", "run_preview"),
    StageSpec("city", "run_city"),
    StageSpec("world", "run_world"),
)

PIPELINE_INTERNAL_MODULES = (
    ROADS_EXTRACT,
    ROADS_RENDER,
    BUILDS_EXTRACT,
    BUILDS_RENDER,
    PREVIEW_ROADS,
    PREVIEW_BUILDS,
    PREVIEW_GRID,
    PREVIEW_CITY,
    CITY_CONSTRUCT,
    CITY_RENDER,
    WORLD_EXPORT,
)

STAGES = {spec.key: spec for spec in ORDERED_STAGE_SPECS}
PIPELINE_STAGE_COMMANDS = tuple(spec.key for spec in ORDERED_STAGE_SPECS)
PIPELINE_STAGE_MODULES = ("pipeline.stages",)
RELOAD_ORDER = (*PIPELINE_DEPENDENCY_MODULES, *PIPELINE_INTERNAL_MODULES, *PIPELINE_STAGE_MODULES)


def stage_module(stage_key: str) -> str:
    if stage_key not in STAGES:
        raise KeyError(f"Unknown pipeline stage: {stage_key}")
    return "pipeline.stages"


def stage_runner_name(stage_key: str) -> str:
    try:
        return STAGES[stage_key].runner
    except KeyError as exc:
        raise KeyError(f"Unknown pipeline stage: {stage_key}") from exc


def stage_runner(stage_key: str):
    return getattr(sys.modules[__name__], stage_runner_name(stage_key))


def _module_runner(module_name: str):
    return importlib.import_module(module_name).run


def noop(*args, **kwargs) -> None:
    """A logger/progress callback that discards its arguments."""


def run_steps(steps, *, logger=None, progress=None, done_label=None):
    """Run labelled stage steps and return their results by key.

    Each step is ``(result_key, progress_label, callable, kwargs)``; the callable
    is invoked with the shared ``logger`` plus its own keyword arguments.
    """
    logger = logger or noop
    progress = progress or noop
    results = {}
    total = len(steps)
    for index, (key, label, run, kwargs) in enumerate(steps):
        progress(index, total, label)
        results[key] = run(logger=logger, **kwargs)
    if done_label is not None:
        progress(total, total, done_label)
    return results


def run_roads(*, logger=None, progress=None):
    return run_steps(
        (
            ("extract", "Extracting road pieces", _module_runner(ROADS_EXTRACT), {}),
            ("render", "Rendering road contact sheet", _module_runner(ROADS_RENDER), {}),
        ),
        logger=logger,
        progress=progress,
        done_label="Road assets ready",
    )


def run_builds(*, logger=None, progress=None):
    return run_steps(
        (
            ("extract", "Extracting building pieces", _module_runner(BUILDS_EXTRACT), {}),
            ("render", "Rendering building contact sheet", _module_runner(BUILDS_RENDER), {}),
        ),
        logger=logger,
        progress=progress,
        done_label="Building assets ready",
    )


def run_preview(*, seed=DEFAULT_SEED, fine=DEFAULT_FINE, preview=0, logger=None, progress=None):
    return run_steps(
        (
            ("road_assets", "Generating road preview assets", _module_runner(PREVIEW_ROADS), {}),
            ("build_assets", "Generating building preview assets", _module_runner(PREVIEW_BUILDS), {}),
            (
                "grid_preview",
                "Rendering road layout preview",
                _module_runner(PREVIEW_GRID),
                {"seed": seed, "fine": fine, "preview": preview},
            ),
            (
                "city_preview",
                "Rendering city layout preview",
                _module_runner(PREVIEW_CITY),
                {"seed": seed, "fine": fine, "preview": preview},
            ),
        ),
        logger=logger,
        progress=progress,
        done_label="Preview ready",
    )


def run_city(*, seed=DEFAULT_SEED, fine=DEFAULT_FINE, logger=None, progress=None):
    return run_steps(
        (
            ("construct", "Building city schematic", _module_runner(CITY_CONSTRUCT), {"seed": seed, "fine": fine}),
            ("render", "Rendering final city", _module_runner(CITY_RENDER), {}),
        ),
        logger=logger,
        progress=progress,
        done_label="City ready",
    )


def run_world(*, seed=DEFAULT_SEED, out=None, logger=None, progress=None):
    return _module_runner(WORLD_EXPORT)(seed=seed, out=out, logger=logger, progress=progress)


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


_STAGE_CLI_PARAMS = {
    "roads": (),
    "builds": (),
    "preview": ("seed", "fine", "preview"),
    "city": ("seed", "fine"),
    "world": ("seed", "out"),
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="stage", required=True)
    for key in PIPELINE_STAGE_COMMANDS:
        runner = stage_runner(key)
        signature = inspect.signature(runner)
        subparser = subparsers.add_parser(key)
        for name in _STAGE_CLI_PARAMS[key]:
            subparser.add_argument(
                f"--{name.replace('_', '-')}",
                default=signature.parameters[name].default,
                **_STAGE_CLI_ARGS[name],
            )

    args = parser.parse_args(argv)
    runner = stage_runner(args.stage)
    kwargs = {name: getattr(args, name) for name in _STAGE_CLI_PARAMS[args.stage]}
    runner(logger=print, **kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
