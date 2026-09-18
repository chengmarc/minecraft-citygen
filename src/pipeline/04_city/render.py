"""Prod pipeline: render one seed's composed city .schem as an isometric PNG."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.algo import DEFAULT_SEED
from config.path import city_render_path, city_schem_path
from config.render import FULL_SCHEM_ISO_BLOCK_H, FULL_SCHEM_ISO_TILE_H, FULL_SCHEM_ISO_TILE_W
from engine.render.isometric import render_schem_visible_iso
from pipeline.stages import noop, run_stage_cli


def run(*, seed=DEFAULT_SEED, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop
    schem = city_schem_path(seed)
    if not os.path.exists(schem):
        raise FileNotFoundError(f"City schematic not found: {schem}. Run Stage 4 construct first.")
    progress(0, 1, "Rendering city schematic")
    im = render_schem_visible_iso(
        schem,
        tile_w=FULL_SCHEM_ISO_TILE_W,
        tile_h=FULL_SCHEM_ISO_TILE_H,
        block_h=FULL_SCHEM_ISO_BLOCK_H,
    )
    out = city_render_path(seed)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.save(out)
    logger(f"saved {out} ({im.width}x{im.height})")
    progress(1, 1, f"seed_{seed}")
    return {"output_path": out, "image_size": im.size}


if __name__ == "__main__":
    run_stage_cli(run, "seed")
