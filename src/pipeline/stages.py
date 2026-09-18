"""The pipeline stage registry and the one runner that executes it.

Each numbered stage is an ordered tuple of :class:`Step` records, each naming
the module whose ``run`` performs it. :func:`run_stage` is the only code that
walks those steps; the CLI (:func:`main`) and the GUI (via
:mod:`pipeline.services`) both call it. The step modules share their helpers
through :mod:`pipeline.step`, never through this registry.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.step import CLI_OPTIONS, add_options, noop


@dataclass(frozen=True)
class Step:
    key: str  # result key in run_stage's return value
    label: str
    module: str  # module whose ``run`` performs the step
    params: tuple[str, ...] = ()  # stage parameters forwarded to ``run``; the CLI exposes those in CLI_OPTIONS


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

STAGES = {
    "roads": (
        Step("extract", "Extracting road pieces", ROADS_EXTRACT, ("save", "road_box", "data_version")),
        Step("render", "Rendering road contact sheet", ROADS_RENDER),
    ),
    "builds": (
        Step("extract", "Extracting building pieces", BUILDS_EXTRACT, ("save", "build_types", "data_version")),
        Step("render", "Rendering building contact sheet", BUILDS_RENDER),
    ),
    "preview": (
        Step("road_assets", "Generating road preview assets", PREVIEW_ROADS),
        Step("build_assets", "Generating building preview assets", PREVIEW_BUILDS),
        Step("grid_preview", "Rendering road layout preview", PREVIEW_GRID, ("seed", "fine", "algo", "preview")),
        Step("city_preview", "Rendering city layout preview", PREVIEW_CITY, ("seed", "fine", "algo", "preview")),
    ),
    "city": (
        Step("construct", "Building city schematic", CITY_CONSTRUCT, ("seed", "fine", "algo", "data_version")),
        Step("render", "Rendering final city", CITY_RENDER, ("seed",)),
    ),
    "world": (
        Step("export", "Exporting Minecraft world", WORLD_EXPORT, ("seed", "save", "out")),
    ),
}

PIPELINE_STAGE_COMMANDS = tuple(STAGES)


def stage_params(stage_key):
    """Every parameter the stage accepts, in first-use order."""
    return tuple(dict.fromkeys(name for step in STAGES[stage_key] for name in step.params))


def run_stage(stage_key, *, logger=None, progress=None, **params):
    """Run every step of ``stage_key`` in order; return each step's result by key.

    Omitted ``params`` fall back to each step's own ``run`` defaults. Each
    step's ``(completed, total, detail)`` progress is forwarded as
    ``progress(step_module, completed, total, detail)``.
    """
    if stage_key not in STAGES:
        raise KeyError(f"Unknown pipeline stage: {stage_key}")
    unknown = set(params) - set(stage_params(stage_key))
    if unknown:
        raise TypeError(f"stage {stage_key!r} got unexpected parameters: {sorted(unknown)}")
    logger = logger or noop
    progress = progress or noop
    results = {}
    for step in STAGES[stage_key]:
        run = importlib.import_module(step.module).run
        kwargs = {name: params[name] for name in step.params if name in params}
        results[step.key] = run(
            logger=logger,
            progress=lambda completed, total, detail, _module=step.module: progress(_module, completed, total, detail),
            **kwargs,
        )
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="stage", required=True)
    for key in PIPELINE_STAGE_COMMANDS:
        # Omitted options stay unset, so each step applies its own default.
        cli_params = [name for name in stage_params(key) if name in CLI_OPTIONS]
        add_options(subparsers.add_parser(key), cli_params, lambda _name: argparse.SUPPRESS)

    params = vars(parser.parse_args(argv))
    run_stage(params.pop("stage"), logger=print, **params)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
