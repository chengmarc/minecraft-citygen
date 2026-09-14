"""Stage 1: extract and render road assets."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.stages import run_stage_cli, run_steps

if __package__ in (None, ""):
    import importlib

    extract = importlib.import_module("pipeline.01_roads.extract")
    render = importlib.import_module("pipeline.01_roads.render")
else:
    from . import extract, render


def run(*, logger=None, progress=None):
    return run_steps(
        (
            ("extract", "Extracting road pieces", extract.run, {}),
            ("render", "Rendering road contact sheet", render.run, {}),
        ),
        logger=logger,
        progress=progress,
        done_label="Road assets ready",
    )


if __name__ == "__main__":
    run_stage_cli(run)
