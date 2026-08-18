"""Prod pipeline: composite the 14 road schematics into one big .schem."""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)  # shared modules live in the repo root

from config_path import GRID_PROD_SCHEM  # noqa: E402
from engine.road_schematic import build, to_schem  # noqa: E402
from engine.schematic_writer import save_sponge_schem  # noqa: E402
from engine import road_network as R  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--fine", type=int, default=R.FINE)
    ap.add_argument("--out", default=None, help="output .schem (default: ./seed_<seed>.schem)")
    args = ap.parse_args()
    out = args.out or os.path.join(GRID_PROD_SCHEM, f"seed_{args.seed}.schem")

    grid, palette, dims, count = build(args.fine, args.seed)
    print(f"seed {args.seed}, fine {args.fine}: placed {count} tiles, "
          f"dims {dims[0]}x{dims[1]}x{dims[2]} (WxHxL), palette {len(palette)}")
    save_sponge_schem(to_schem(grid, palette, dims), out)
    print("saved", out)


if __name__ == "__main__":
    main()
