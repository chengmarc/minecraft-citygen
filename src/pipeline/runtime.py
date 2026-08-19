"""Shared runtime helpers for in-process pipeline execution."""

from __future__ import annotations

import importlib
import os
import sys
import threading
from contextlib import contextmanager

from pipeline.stages import RELOAD_ORDER

PIPELINE_LOCK = threading.RLock()


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
