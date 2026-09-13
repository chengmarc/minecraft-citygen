"""Stage 4: build and render the final city."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.algo import DEFAULT_SEED, FINE as DEFAULT_FINE
from pipeline.stages import noop, run_stage_cli

if __package__ in (None, ""):
    import importlib

    construct = importlib.import_module("pipeline.04_city.construct")
    render = importlib.import_module("pipeline.04_city.render")
else:
    from . import construct, render


def run(*, seed=DEFAULT_SEED, fine=DEFAULT_FINE, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop
    progress(0, 2, "Building city schematic")
    construct_result = construct.run(seed=seed, fine=fine, logger=logger)
    progress(1, 2, "Rendering final city")
    render_result = render.run(logger=logger)
    progress(2, 2, "City ready")
    return {"construct": construct_result, "render": render_result}


if __name__ == "__main__":
    run_stage_cli(run, "seed", "fine")
