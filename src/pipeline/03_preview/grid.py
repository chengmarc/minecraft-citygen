"""Stage 3 helper: compose the vector road tiles into a grid preview."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.algo import DEFAULT_SEED, FINE as DEFAULT_FINE
from config.path import grid_preview_path
from engine.core.road_network import gen_networks, make_size
from engine.render.road_layout import compose, load_assets
from pipeline.stages import noop, run_stage_cli


def run(*, seed=DEFAULT_SEED, fine=DEFAULT_FINE, preview=0, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop
    progress(0, 1, "Rendering road layout preview")
    size = make_size(fine)
    net = gen_networks(seed, size=size)
    logger(f"big rows={sorted(net['big_rows'])} cols={sorted(net['big_cols'])}")
    logger(f"small rows={sorted(net['small_rows'])} cols={sorted(net['small_cols'])}")
    grid = compose(net, load_assets())
    if preview:
        grid = grid.resize((preview, preview), Image.Resampling.NEAREST)
    out = grid_preview_path(seed)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    grid.save(out)
    logger(f"saved {out} {grid.size}")
    progress(1, 1, "Rendered road layout preview")
    return {"output_path": out, "image_size": grid.size}


if __name__ == "__main__":
    run_stage_cli(run, "seed", "fine", "preview")
