"""Sim pipeline: compose the vector road tiles into a grid preview."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.config_algo import DEFAULT_SEED, FINE as DEFAULT_FINE
from config.config_path import GRID_SIM
from engine.core.road_network import compose, gen_networks, load_assets, make_size
from pipeline.stages import noop, run_stage_cli


def run(*, seed=DEFAULT_SEED, fine=DEFAULT_FINE, preview=0, logger=None):
    logger = logger or noop
    size = make_size(fine, even=True)
    net = gen_networks(seed, size=size)
    logger(f"big rows={sorted(net['big_rows'])} cols={sorted(net['big_cols'])}")
    logger(f"small rows={sorted(net['small_rows'])} cols={sorted(net['small_cols'])}")
    grid = compose(net, load_assets())
    if preview:
        grid = grid.resize((preview, preview), Image.Resampling.NEAREST)
    out = os.path.join(GRID_SIM, f"seed_{seed}_preview.png")
    os.makedirs(GRID_SIM, exist_ok=True)
    grid.save(out)
    logger(f"saved {out} {grid.size}")
    return {"output_path": out, "image_size": grid.size}


if __name__ == "__main__":
    run_stage_cli(run, "seed", "fine", "preview")
