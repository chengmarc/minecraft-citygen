"""Sim pipeline: compose the vector road tiles into a grid preview."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PIL import Image

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.config_algo import DEFAULT_SEED, FINE as DEFAULT_FINE
from config.config_path import GRID_SIM
from engine import road_network as R


def run(*, seed=DEFAULT_SEED, fine=DEFAULT_FINE, preview=0, logger=None):
    size = R.make_size(fine, even=True)
    net = R.gen_networks(seed, size=size)
    if logger is not None:
        logger(f"big rows={sorted(net['big_rows'])} cols={sorted(net['big_cols'])}")
        logger(f"small rows={sorted(net['small_rows'])} cols={sorted(net['small_cols'])}")
    grid = R.compose(net, R.load_assets())
    if preview:
        grid = grid.resize((preview, preview), Image.Resampling.NEAREST)
    out = os.path.join(GRID_SIM, f"seed_{seed}_preview.png")
    grid.save(out)
    if logger is not None:
        logger("saved", out, grid.size)
    return {"output_path": out, "image_size": grid.size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--fine", type=int, default=DEFAULT_FINE, help="fine grid edge in cells (even)")
    ap.add_argument("--preview", type=int, default=0, help="edge of the preview png (0 = full res)")
    args = ap.parse_args()
    run(seed=args.seed, fine=args.fine, preview=args.preview, logger=print)


if __name__ == "__main__":
    main()
