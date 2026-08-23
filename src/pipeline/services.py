"""Shared in-process pipeline services used by both the GUI and CLI entry points."""

from __future__ import annotations

import importlib

from pipeline.runtime import configured_environment
from pipeline.stages import stage_module

# Stage module paths used directly by the GUI preview buttons. Other callers
# resolve stage modules on demand via stage_module(<key>).
ROADS_SIMULATION = stage_module("roads_simulation")
BUILDS_SIMULATION = stage_module("builds_simulation")
GRID_SIMULATION = stage_module("grid_simulation")
CITY_SIMULATION = stage_module("city_simulation")
ROADS_EXTRACT = stage_module("roads_extract")
ROADS_RENDER = stage_module("roads_render")
BUILDS_EXTRACT = stage_module("builds_extract")
BUILDS_RENDER = stage_module("builds_render")
CITY_CONSTRUCT = stage_module("city_construct")
CITY_RENDER = stage_module("city_render")


def _load_stage_runner(stage_key):
    return importlib.import_module(stage_module(stage_key)).run


def _coerce_int(value, name):
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer.") from exc


def call_with_env(fn, *, env_overrides=None, **kwargs):
    with configured_environment(env_overrides):
        return fn(**kwargs)


def _run_stage(stage_key, *, env_overrides=None, **kwargs):
    return call_with_env(_load_stage_runner(stage_key), env_overrides=env_overrides, **kwargs)


def _run_seeded_stage(stage_key, seed, fine, *, env_overrides=None, logger=None):
    return _run_stage(
        stage_key,
        env_overrides=env_overrides,
        seed=_coerce_int(seed, "Seed"),
        fine=_coerce_int(fine, "Fine"),
        logger=logger,
    )


def _progress_adapter(progress, stage_key):
    """Tag a stage's ``(completed, total, detail)`` ticks with its module path.

    The GUI keys off the module to show which script is running and its step,
    e.g. ``Stage 1/4 - pipeline/01_roads/extract.py - ...``.
    """
    if progress is None:
        return None
    module = stage_module(stage_key)
    return lambda completed, total, detail: progress(module, completed, total, detail)


def _run_extraction_pipeline(extract_stage, render_stage, *, env_overrides=None, logger=None, progress=None):
    extract_result = _run_stage(
        extract_stage,
        env_overrides=env_overrides,
        logger=logger,
        progress=_progress_adapter(progress, extract_stage),
    )
    render_result = _run_stage(
        render_stage,
        env_overrides=env_overrides,
        logger=logger,
        progress=_progress_adapter(progress, render_stage),
    )
    return {"extract": extract_result, "render": render_result}


def run_roads_simulation_stage(*, env_overrides=None, logger=None):
    return _run_stage("roads_simulation", env_overrides=env_overrides, logger=logger)


def run_builds_simulation_stage(*, env_overrides=None, logger=None):
    return _run_stage("builds_simulation", env_overrides=env_overrides, logger=logger)


def run_grid_simulation_stage(seed, fine, *, env_overrides=None, logger=None):
    return _run_seeded_stage("grid_simulation", seed, fine, env_overrides=env_overrides, logger=logger)


def run_city_simulation_stage(seed, fine, *, env_overrides=None, logger=None):
    return _run_seeded_stage("city_simulation", seed, fine, env_overrides=env_overrides, logger=logger)


def run_city_construct_stage(seed, fine, *, env_overrides=None, logger=None, progress=None):
    with configured_environment(env_overrides):
        return _load_stage_runner("city_construct")(
            seed=_coerce_int(seed, "Seed"),
            fine=_coerce_int(fine, "Fine"),
            logger=logger,
            progress=_progress_adapter(progress, "city_construct"),
        )


def run_city_render_stage(*, env_overrides=None, logger=None, progress=None):
    return _run_stage(
        "city_render",
        env_overrides=env_overrides,
        logger=logger,
        progress=_progress_adapter(progress, "city_render"),
    )


def run_road_extraction_pipeline(*, env_overrides=None, logger=None, progress=None):
    return _run_extraction_pipeline(
        "roads_extract",
        "roads_render",
        env_overrides=env_overrides,
        logger=logger,
        progress=progress,
    )


def run_build_extraction_pipeline(*, env_overrides=None, logger=None, progress=None):
    return _run_extraction_pipeline(
        "builds_extract",
        "builds_render",
        env_overrides=env_overrides,
        logger=logger,
        progress=progress,
    )
