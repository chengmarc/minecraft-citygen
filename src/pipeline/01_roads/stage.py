"""Stage 1: extract and render road assets."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.stages import noop, run_stage_cli

if __package__ in (None, ""):
    import importlib

    extract = importlib.import_module("pipeline.01_roads.extract")
    render = importlib.import_module("pipeline.01_roads.render")
else:
    from . import extract, render


def run(*, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop
    progress(0, 2, "Extracting road pieces")
    extract_result = extract.run(logger=logger)
    progress(1, 2, "Rendering road contact sheet")
    render_result = render.run(logger=logger)
    progress(2, 2, "Road assets ready")
    return {"extract": extract_result, "render": render_result}


if __name__ == "__main__":
    run_stage_cli(run)
