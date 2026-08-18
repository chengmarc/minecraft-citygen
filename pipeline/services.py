"""Shared in-process pipeline services used by both the GUI and CLI entry points."""

from __future__ import annotations

import importlib

from pipeline.runtime import configured_environment

ROADS_SIMULATION = "pipeline.01_roads_simulation"
ROADS_EXTRACT = "pipeline.01_roads_extract"
ROADS_RENDER = "pipeline.01_roads_render"
BUILDS_SIMULATION = "pipeline.02_builds_simulation"
BUILDS_EXTRACT = "pipeline.02_builds_extract"
BUILDS_RENDER = "pipeline.02_builds_render"
GRID_SIMULATION = "pipeline.03_grid_simulation"
GRID_CONSTRUCT = "pipeline.03_grid_construct"
GRID_RENDER = "pipeline.03_grid_render"
CITY_SIMULATION = "pipeline.04_city_simulation"
CITY_CONSTRUCT = "pipeline.04_city_construct"
CITY_RENDER = "pipeline.04_city_render"


def _stage_module(name):
    return importlib.import_module(name)


def call_with_env(fn, *, env_overrides=None, **kwargs):
    with configured_environment(env_overrides):
        return fn(**kwargs)


def run_roads_simulation_stage(*, env_overrides=None, logger=None):
    return call_with_env(_stage_module(ROADS_SIMULATION).run, env_overrides=env_overrides, logger=logger)


def run_builds_simulation_stage(*, env_overrides=None, logger=None):
    return call_with_env(_stage_module(BUILDS_SIMULATION).run, env_overrides=env_overrides, logger=logger)


def run_grid_simulation_stage(seed, fine, *, env_overrides=None, logger=None):
    return call_with_env(_stage_module(GRID_SIMULATION).run, env_overrides=env_overrides, seed=seed, fine=fine, logger=logger)


def run_city_simulation_stage(seed, fine, *, env_overrides=None, logger=None):
    return call_with_env(_stage_module(CITY_SIMULATION).run, env_overrides=env_overrides, seed=seed, fine=fine, logger=logger)


def run_city_construct_stage(seed, fine, *, env_overrides=None, logger=None):
    return call_with_env(_stage_module(CITY_CONSTRUCT).run, env_overrides=env_overrides, seed=seed, fine=fine, logger=logger)


def run_city_render_stage(*, env_overrides=None, logger=None):
    return call_with_env(_stage_module(CITY_RENDER).run, env_overrides=env_overrides, logger=logger)


def run_preview_pipeline(seed, fine, *, env_overrides=None, logger=None):
    roads_result = run_roads_simulation_stage(env_overrides=env_overrides, logger=logger)
    builds_result = run_builds_simulation_stage(env_overrides=env_overrides, logger=logger)
    grid_result = run_grid_simulation_stage(seed, fine, env_overrides=env_overrides, logger=logger)
    city_result = run_city_simulation_stage(seed, fine, env_overrides=env_overrides, logger=logger)
    return {"roads": roads_result, "builds": builds_result, "grid": grid_result, "city": city_result}


def run_render_pipeline(seed, fine, *, env_overrides=None, logger=None):
    construct_result = run_city_construct_stage(seed, fine, env_overrides=env_overrides, logger=logger)
    render_result = run_city_render_stage(env_overrides=env_overrides, logger=logger)
    return {"construct": construct_result, "render": render_result}


def run_road_extraction_pipeline(*, env_overrides=None, logger=None, progress=None):
    extract_progress = None if progress is None else (
        lambda completed, total, label: progress("Extracting", completed, total, label)
    )
    render_progress = None if progress is None else (
        lambda completed, total, label: progress("Rendering", completed, total, label)
    )
    extract_result = call_with_env(_stage_module(ROADS_EXTRACT).run, env_overrides=env_overrides, logger=logger, progress=extract_progress)
    render_result = call_with_env(_stage_module(ROADS_RENDER).run, env_overrides=env_overrides, logger=logger, progress=render_progress)
    return {"extract": extract_result, "render": render_result}


def run_build_extraction_pipeline(*, env_overrides=None, logger=None, progress=None):
    extract_progress = None if progress is None else (
        lambda completed, total, label: progress("Extracting", completed, total, label)
    )
    render_progress = None if progress is None else (
        lambda completed, total, label: progress("Rendering", completed, total, label)
    )
    extract_result = call_with_env(_stage_module(BUILDS_EXTRACT).run, env_overrides=env_overrides, logger=logger, progress=extract_progress)
    render_result = call_with_env(_stage_module(BUILDS_RENDER).run, env_overrides=env_overrides, logger=logger, progress=render_progress)
    return {"extract": extract_result, "render": render_result}
