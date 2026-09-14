"""Stage 3: generate road-grid and city-layout previews."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.algo import DEFAULT_SEED, FINE as DEFAULT_FINE
from pipeline.stages import run_stage_cli, run_steps

if __package__ in (None, ""):
    import importlib

    roads = importlib.import_module("pipeline.03_preview.roads")
    builds = importlib.import_module("pipeline.03_preview.builds")
    grid = importlib.import_module("pipeline.03_preview.grid")
    city = importlib.import_module("pipeline.03_preview.city")
else:
    from . import builds, city, grid, roads


def run(*, seed=DEFAULT_SEED, fine=DEFAULT_FINE, preview=0, logger=None, progress=None):
    return run_steps(
        (
            ("road_assets", "Generating road preview assets", roads.run, {}),
            ("build_assets", "Generating building preview assets", builds.run, {}),
            ("grid_preview", "Rendering road layout preview", grid.run, {"seed": seed, "fine": fine, "preview": preview}),
            ("city_preview", "Rendering city layout preview", city.run, {"seed": seed, "fine": fine, "preview": preview}),
        ),
        logger=logger,
        progress=progress,
        done_label="Preview ready",
    )


if __name__ == "__main__":
    run_stage_cli(run, "seed", "fine", "preview")
