"""Prod pipeline: render composed city .schem files as isometric PNGs."""

from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.path import CITY_PROD
from config.render import FULL_SCHEM_ISO_BLOCK_H, FULL_SCHEM_ISO_TILE_H, FULL_SCHEM_ISO_TILE_W
from engine.render.isometric import render_schem_visible_iso
from pipeline.stages import noop, run_stage_cli

SCHEM = CITY_PROD


def run(*, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop
    os.makedirs(CITY_PROD, exist_ok=True)
    outputs = []
    paths = sorted(glob.glob(os.path.join(SCHEM, "*.schem")))
    total = len(paths)
    if total > 0:
        progress(0, total, "Rendering city schematic")
    for index, path in enumerate(paths, start=1):
        name = os.path.splitext(os.path.basename(path))[0]
        im = render_schem_visible_iso(
            path,
            tile_w=FULL_SCHEM_ISO_TILE_W,
            tile_h=FULL_SCHEM_ISO_TILE_H,
            block_h=FULL_SCHEM_ISO_BLOCK_H,
        )
        out = os.path.join(CITY_PROD, name + ".png")
        im.save(out)
        outputs.append(out)
        logger(f"saved {out} ({im.width}x{im.height})")
        progress(index, total, name)
    return {"count": len(outputs), "outputs": outputs}


if __name__ == "__main__":
    run_stage_cli(run)
