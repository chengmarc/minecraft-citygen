"""Prod pipeline: composite the road schematics into one big .schem."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.config_algo import DEFAULT_SEED, FINE as DEFAULT_FINE
from config.config_path import GRID_PROD_SCHEM
from engine.road_schematic import build, to_schem
from engine.schematic_writer import save_sponge_schem


def run(*, seed=DEFAULT_SEED, fine=DEFAULT_FINE, out=None, logger=None):
    out = out or os.path.join(GRID_PROD_SCHEM, f"seed_{seed}.schem")
    grid, palette, dims, count = build(fine, seed)
    if logger is not None:
        logger(
            f"seed {seed}, fine {fine}: placed {count} tiles, "
            f"dims {dims[0]}x{dims[1]}x{dims[2]} (WxHxL), palette {len(palette)}"
        )
    save_sponge_schem(to_schem(grid, palette, dims), out)
    if logger is not None:
        logger("saved", out)
    return {"output_path": out, "tile_count": count, "dims": dims}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--fine", type=int, default=DEFAULT_FINE)
    ap.add_argument("--out", default=None, help="output .schem (default: ./seed_<seed>.schem)")
    args = ap.parse_args()
    run(seed=args.seed, fine=args.fine, out=args.out, logger=print)


if __name__ == "__main__":
    main()
