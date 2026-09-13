"""Stage 3: generate road-grid and city-layout previews."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.algo import DEFAULT_SEED, FINE as DEFAULT_FINE
from pipeline.stages import noop, run_stage_cli

if __package__ in (None, ""):
    import importlib

    roads = importlib.import_module("pipeline.03_preview.roads")
    builds = importlib.import_module("pipeline.03_preview.builds")
    grid = importlib.import_module("pipeline.03_preview.grid")
    city = importlib.import_module("pipeline.03_preview.city")
else:
    from . import builds, city, grid, roads


def run(*, seed=DEFAULT_SEED, fine=DEFAULT_FINE, preview=0, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop

    def step(completed, label):
        progress(completed, 4, label)

    step(0, "Generating road preview assets")
    road_assets = roads.run(logger=logger)

    step(1, "Generating building preview assets")
    build_assets = builds.run(logger=logger)

    step(2, "Rendering road layout preview")
    grid_preview = grid.run(seed=seed, fine=fine, preview=preview, logger=logger)

    step(3, "Rendering city layout preview")
    city_preview = city.run(seed=seed, fine=fine, preview=preview, logger=logger)

    step(4, "Preview ready")
    return {
        "road_assets": road_assets,
        "build_assets": build_assets,
        "grid_preview": grid_preview,
        "city_preview": city_preview,
    }


if __name__ == "__main__":
    run_stage_cli(run, "seed", "fine", "preview")
