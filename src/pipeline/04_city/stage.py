"""Stage 4: build and render the final city."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.algo import DEFAULT_SEED, FINE as DEFAULT_FINE
from pipeline.stages import run_stage_cli, run_steps

if __package__ in (None, ""):
    import importlib

    construct = importlib.import_module("pipeline.04_city.construct")
    render = importlib.import_module("pipeline.04_city.render")
else:
    from . import construct, render


def run(*, seed=DEFAULT_SEED, fine=DEFAULT_FINE, logger=None, progress=None):
    return run_steps(
        (
            ("construct", "Building city schematic", construct.run, {"seed": seed, "fine": fine}),
            ("render", "Rendering final city", render.run, {}),
        ),
        logger=logger,
        progress=progress,
        done_label="City ready",
    )


if __name__ == "__main__":
    run_stage_cli(run, "seed", "fine")
