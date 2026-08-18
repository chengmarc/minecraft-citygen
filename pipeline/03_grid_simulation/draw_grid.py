"""Sim pipeline: compose the vector road tiles into a grid preview.

Renders the grid from 01_roads_simulation/ at the shared simulation scale
(9 px per fine cell by default) and saves it as seed_<seed>_preview.png.
"""
import argparse
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))  # shared modules live in the repo root
from config.config_algo import DEFAULT_SEED
from engine import road_network as R
from config.config_path import GRID_SIM


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--fine", type=int, default=R.FINE, help="fine grid edge in cells (even)")
    ap.add_argument("--preview", type=int, default=0, help="edge of the preview png (0 = full res)")
    args = ap.parse_args()

    R.set_size(args.fine, even=True)   # keep it even so the coarse grid is exact

    net = R.gen_networks(args.seed)
    print(f"big rows={sorted(net['big_rows'])} cols={sorted(net['big_cols'])}")
    print(f"small rows={sorted(net['small_rows'])} cols={sorted(net['small_cols'])}")

    grid = R.compose(net, R.load_assets())
    if args.preview:
        grid = grid.resize((args.preview, args.preview), Image.Resampling.NEAREST)
    out = os.path.join(GRID_SIM, f"seed_{args.seed}_preview.png")
    grid.save(out)
    print("saved", out, grid.size)


if __name__ == "__main__":
    main()
