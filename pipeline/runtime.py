"""Shared runtime helpers for in-process pipeline execution."""

from __future__ import annotations

import importlib
import os
import sys
import threading
from contextlib import contextmanager

PIPELINE_LOCK = threading.RLock()

RELOAD_ORDER = [
    "config.config_algo",
    "config.config_world",
    "engine.road_network",
    "engine.city_layout",
    "engine.road_schematic",
    "engine.building_schematic",
    "engine.anvil_world_reader",
    "pipeline.01_roads_simulation",
    "pipeline.02_builds_simulation",
    "pipeline.03_grid_simulation",
    "pipeline.04_city_simulation",
    "pipeline.01_roads_extract",
    "pipeline.01_roads_render",
    "pipeline.02_builds_extract",
    "pipeline.02_builds_render",
    "pipeline.03_grid_construct",
    "pipeline.03_grid_render",
    "pipeline.04_city_construct",
    "pipeline.04_city_render",
]


def reload_pipeline_modules():
    for name in RELOAD_ORDER:
        module = sys.modules.get(name)
        if module is not None:
            importlib.reload(module)


@contextmanager
def configured_environment(env_overrides=None):
    env_overrides = env_overrides or {}
    previous = {key: os.environ.get(key) for key in env_overrides}
    with PIPELINE_LOCK:
        try:
            for key, value in env_overrides.items():
                os.environ[key] = value
            reload_pipeline_modules()
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            reload_pipeline_modules()
