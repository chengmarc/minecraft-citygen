"""Prod pipeline: composite the road schematics into one big .schem."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.config_algo import DEFAULT_SEED, FINE as DEFAULT_FINE
from config.config_path import GRID_PROD
from engine.road_schematic import build, to_schem
from engine.schematic_writer import save_sponge_schem
from pipeline.stages import noop, run_stage_cli


def run(*, seed=DEFAULT_SEED, fine=DEFAULT_FINE, out=None, logger=None):
    logger = logger or noop
    out = out or os.path.join(GRID_PROD, f"seed_{seed}.schem")
    grid, palette, dims, count, road_ground_offset, block_entities = build(fine, seed)
    logger(
        f"seed {seed}, fine {fine}: placed {count} tiles, "
        f"dims {dims[0]}x{dims[1]}x{dims[2]} (WxHxL), palette {len(palette)}"
    )
    save_sponge_schem(to_schem(grid, palette, dims, road_ground_offset, block_entities), out)
    logger(f"saved {out}")
    return {"output_path": out, "tile_count": count, "dims": dims}


if __name__ == "__main__":
    run_stage_cli(run, "seed", "fine", "out")
