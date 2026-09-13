"""Stage 5: export the final city as a playable world."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.algo import DEFAULT_SEED
from pipeline.stages import run_stage_cli

if __package__ in (None, ""):
    import importlib

    export = importlib.import_module("pipeline.05_world.export")
else:
    from . import export


def run(*, seed=DEFAULT_SEED, out=None, logger=None, progress=None):
    return export.run(seed=seed, out=out, logger=logger, progress=progress)


if __name__ == "__main__":
    run_stage_cli(run, "seed", "out")
