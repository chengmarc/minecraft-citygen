"""Stage 2: extract and render building assets."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.stages import noop, run_stage_cli

if __package__ in (None, ""):
    import importlib

    extract = importlib.import_module("pipeline.02_builds.extract")
    render = importlib.import_module("pipeline.02_builds.render")
else:
    from . import extract, render


def run(*, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop
    progress(0, 2, "Extracting building pieces")
    extract_result = extract.run(logger=logger)
    progress(1, 2, "Rendering building contact sheet")
    render_result = render.run(logger=logger)
    progress(2, 2, "Building assets ready")
    return {"extract": extract_result, "render": render_result}


if __name__ == "__main__":
    run_stage_cli(run)
