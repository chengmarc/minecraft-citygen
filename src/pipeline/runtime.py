"""Shared runtime helpers for in-process pipeline execution.

Configuration model and its invariant
--------------------------------------
The config modules (``config.algo``, ``config.world``, ...) read
their values from ``MC_CITY_*`` environment variables *at import time* and expose
them as module-level constants. The engine and pipeline modules bind those
constants at *their* import time too. This keeps stage code simple, but it means
a config change only takes effect after the affected modules are re-imported.

``configured_environment`` bridges that gap: it temporarily sets the requested
environment overrides, reloads every module in :data:`RELOAD_ORDER` (dependencies
before dependents, so rebound constants are consistent), yields, then restores the
previous environment and reloads once more to return the process to its baseline
configuration.

Because environment variables and imported modules are *process-global* state,
this mechanism is inherently single-writer:

- ``PIPELINE_LOCK`` serializes runs so two overridden pipelines never interleave.
- It does **not** make concurrent pipelines with *different* overrides safe --
  the lock guarantees one-at-a-time execution, not per-thread isolation. Callers
  must run overridden stages one at a time (as the GUI job queue does).

If per-call configuration isolation is ever needed, the durable fix is to thread
an explicit config object through the stages instead of reloading modules.
"""

from __future__ import annotations

import importlib
import os
import sys
import threading
from contextlib import contextmanager

from pipeline.stages import RELOAD_ORDER

# Serializes overridden pipeline runs; config lives in process-global state, so
# only one configured_environment block may be active at a time.
PIPELINE_LOCK = threading.RLock()


def reload_pipeline_modules():
    """Re-import config/engine/pipeline modules so they rebind current env config.

    Modules are reloaded in dependency order (see RELOAD_ORDER) so a dependent
    never observes a half-updated dependency.
    """
    for name in RELOAD_ORDER:
        module = sys.modules.get(name)
        if module is not None:
            importlib.reload(module)


@contextmanager
def configured_environment(env_overrides=None):
    """Apply ``MC_CITY_*`` overrides for the duration of the block, then restore.

    Holds :data:`PIPELINE_LOCK` for the whole block: the overrides mutate global
    ``os.environ`` and reload shared modules, so the body must run in isolation.
    """
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
