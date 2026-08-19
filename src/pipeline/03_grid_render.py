"""Prod pipeline: render composed grid .schem files as isometric PNGs."""

from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.config_path import GRID_PROD, GRID_PROD_SCHEM
from config.config_render import FULL_SCHEM_ISO_BLOCK_H, FULL_SCHEM_ISO_TILE_H, FULL_SCHEM_ISO_TILE_W
from engine.isometric_renderer import render_schem_visible_iso

SCHEM = GRID_PROD_SCHEM


def run(*, logger=None, progress=None):
    os.makedirs(GRID_PROD, exist_ok=True)
    outputs = []
    paths = sorted(glob.glob(os.path.join(SCHEM, "*.schem")))
    total = len(paths)
    for index, path in enumerate(paths, start=1):
        name = os.path.splitext(os.path.basename(path))[0]
        im = render_schem_visible_iso(
            path,
            tile_w=FULL_SCHEM_ISO_TILE_W,
            tile_h=FULL_SCHEM_ISO_TILE_H,
            block_h=FULL_SCHEM_ISO_BLOCK_H,
        )
        out = os.path.join(GRID_PROD, name + "_render.png")
        im.save(out)
        outputs.append(out)
        if logger is not None:
            logger(f"saved {out} ({im.width}x{im.height})")
        if progress is not None:
            progress(index, total, name)
    return {"count": len(outputs), "outputs": outputs}


def main():
    run(logger=print)


if __name__ == "__main__":
    main()
