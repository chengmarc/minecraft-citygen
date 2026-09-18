"""Run pipeline stages in-process for the GUI.

Per-run settings -- the :class:`config.algo.Algo` knobs, the source save, the
extraction regions, the stamped DataVersion -- are ordinary stage parameters,
so a run changes no process-global state and needs no module reloading.

``PIPELINE_LOCK`` still serializes runs: every stage reads and writes the same
artifact directories, so two runs must never interleave.
"""

from __future__ import annotations

import threading

from pipeline import stages

PIPELINE_LOCK = threading.RLock()

_INTEGER_PARAMS = {"seed": "Seed", "fine": "Fine", "preview": "Preview"}


def _coerce_int(value, label):
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer.") from exc


def run_stage(stage_key, *, logger=None, progress=None, **params):
    """:func:`pipeline.stages.run_stage`, one run at a time.

    GUI inputs arrive as text, so integer parameters are coerced first.
    """
    params = {
        name: _coerce_int(value, _INTEGER_PARAMS[name]) if name in _INTEGER_PARAMS else value
        for name, value in params.items()
    }
    with PIPELINE_LOCK:
        return stages.run_stage(stage_key, logger=logger, progress=progress, **params)
