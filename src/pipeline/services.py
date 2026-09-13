"""Shared in-process pipeline services used by both the GUI and CLI entry points."""

from __future__ import annotations

import importlib

from pipeline.runtime import configured_environment
from pipeline.stages import stage_module

# Stage module paths used directly by the GUI tabs. Other callers
# resolve stage modules on demand via stage_module(<key>).
ROADS = stage_module("roads")
BUILDS = stage_module("builds")
PREVIEW = stage_module("preview")
CITY = stage_module("city")
WORLD = stage_module("world")

ROADS_EXTRACT = "pipeline.01_roads.extract"
ROADS_RENDER = "pipeline.01_roads.render"
BUILDS_EXTRACT = "pipeline.02_builds.extract"
BUILDS_RENDER = "pipeline.02_builds.render"
CITY_CONSTRUCT = "pipeline.04_city.construct"
CITY_RENDER = "pipeline.04_city.render"
WORLD_EXPORT = WORLD


def _load_stage_runner(stage_key):
    return importlib.import_module(stage_module(stage_key)).run


def _load_module_runner(module):
    return importlib.import_module(module).run


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


def _progress_adapter(progress, stage_key):
    """Tag a stage's ``(completed, total, detail)`` ticks with its module path.

    The GUI keys off the module to show which script is running and its step,
    e.g. ``Stage 1/N - pipeline/01_roads/extract.py - ...``.
    """
    if progress is None:
        return None
    module = stage_module(stage_key)
    return lambda completed, total, detail: progress(module, completed, total, detail)


def _progress_adapter_for_module(progress, module):
    if progress is None:
        return None
    return lambda completed, total, detail: progress(module, completed, total, detail)


def _run_module(module, *, env_overrides=None, **kwargs):
    return call_with_env(_load_module_runner(module), env_overrides=env_overrides, **kwargs)


def _run_extraction_pipeline(extract_module, render_module, *, env_overrides=None, logger=None, progress=None):
    extract_result = _run_module(
        extract_module,
        env_overrides=env_overrides,
        logger=logger,
        progress=_progress_adapter_for_module(progress, extract_module),
    )
    render_result = _run_module(
        render_module,
        env_overrides=env_overrides,
        logger=logger,
        progress=_progress_adapter_for_module(progress, render_module),
    )
    return {"extract": extract_result, "render": render_result}


def run_preview_stage(seed, fine, *, env_overrides=None, logger=None, progress=None):
    with configured_environment(env_overrides):
        return _load_stage_runner("preview")(
            seed=_coerce_int(seed, "Seed"),
            fine=_coerce_int(fine, "Fine"),
            logger=logger,
            progress=_progress_adapter(progress, "preview"),
        )


def run_city_construct_stage(seed, fine, *, env_overrides=None, logger=None, progress=None):
    with configured_environment(env_overrides):
        return _load_module_runner(CITY_CONSTRUCT)(
            seed=_coerce_int(seed, "Seed"),
            fine=_coerce_int(fine, "Fine"),
            logger=logger,
            progress=_progress_adapter_for_module(progress, CITY_CONSTRUCT),
        )


def run_city_render_stage(*, env_overrides=None, logger=None, progress=None):
    return _run_module(
        CITY_RENDER,
        env_overrides=env_overrides,
        logger=logger,
        progress=_progress_adapter_for_module(progress, CITY_RENDER),
    )


def run_world_export_stage(seed, *, env_overrides=None, logger=None, progress=None):
    with configured_environment(env_overrides):
        return _load_stage_runner("world")(
            seed=_coerce_int(seed, "Seed"),
            logger=logger,
            progress=_progress_adapter(progress, "world"),
        )


def run_roads_stage(*, env_overrides=None, logger=None, progress=None):
    return _run_extraction_pipeline(
        ROADS_EXTRACT,
        ROADS_RENDER,
        env_overrides=env_overrides,
        logger=logger,
        progress=progress,
    )


def run_builds_stage(*, env_overrides=None, logger=None, progress=None):
    return _run_extraction_pipeline(
        BUILDS_EXTRACT,
        BUILDS_RENDER,
        env_overrides=env_overrides,
        logger=logger,
        progress=progress,
    )


def run_city_stage(seed, fine, *, env_overrides=None, logger=None, progress=None):
    construct_result = run_city_construct_stage(
        seed,
        fine,
        env_overrides=env_overrides,
        logger=logger,
        progress=progress,
    )
    render_result = run_city_render_stage(
        env_overrides=env_overrides,
        logger=logger,
        progress=progress,
    )
    return {"construct": construct_result, "render": render_result}


def run_world_stage(seed, *, env_overrides=None, logger=None, progress=None):
    return run_world_export_stage(seed, env_overrides=env_overrides, logger=logger, progress=progress)


# Backward-compatible names for callers that still use the old extraction
# service labels. The public pipeline model is stage-based above.
run_road_extraction_pipeline = run_roads_stage
run_build_extraction_pipeline = run_builds_stage
