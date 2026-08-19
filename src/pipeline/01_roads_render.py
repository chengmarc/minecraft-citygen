"""Prod pipeline: render exported road .schem assets as isometric PNGs."""

from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.config_path import ROADS_PROD
from config.config_render import ROAD_ASSET_ISO_BLOCK_H, ROAD_ASSET_ISO_TILE_H, ROAD_ASSET_ISO_TILE_W
from engine.render_isometric import render_cells_visible_iso, write_contact
from engine.schematic_reader import decode_schem_cells

SCHEM = ROADS_PROD


def run(*, logger=None, progress=None):
    os.makedirs(ROADS_PROD, exist_ok=True)
    images = []
    paths = sorted(glob.glob(os.path.join(SCHEM, "*.schem")))
    total = len(paths)
    for index, path in enumerate(paths, start=1):
        name = os.path.splitext(os.path.basename(path))[0]
        im = render_cells_visible_iso(
            decode_schem_cells(path),
            tile_w=ROAD_ASSET_ISO_TILE_W,
            tile_h=ROAD_ASSET_ISO_TILE_H,
            block_h=ROAD_ASSET_ISO_BLOCK_H,
        )
        out = os.path.join(ROADS_PROD, name + ".png")
        im.save(out)
        images.append((name, im))
        if logger is not None:
            logger(f"saved {out} ({im.width}x{im.height})")
        if progress is not None:
            progress(index, total, name)

    contact = os.path.join(ROADS_PROD, "_contact_sheet.png")
    if progress is not None:
        progress(0, 1, "Rendering road contact sheet...")
    write_contact(images, contact, cols=5, cell_w=220, cell_h=190)
    if progress is not None:
        progress(1, 1, "Rendered road contact sheet.")
    if logger is not None:
        logger(f"rendered {len(images)} roads -> {contact}")
    return {"count": len(images), "contact_sheet": contact}


def main():
    run(logger=print)


if __name__ == "__main__":
    main()
