"""Prod pipeline: render exported road .schem assets as isometric PNGs."""

from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.path import ROADS_CONTACT_SHEET, ROADS_RENDERS, ROADS_SCHEM
from config.render import ROAD_ASSET_ISO_BLOCK_H, ROAD_ASSET_ISO_TILE_H, ROAD_ASSET_ISO_TILE_W
from engine.render.isometric import render_cells_visible_iso
from engine.schematic.reader import decode_schem_cells
from pipeline.rendering import render_contact_sheet
from pipeline.step import run_stage_cli

def run(*, logger=None, progress=None):
    paths = sorted(glob.glob(os.path.join(ROADS_SCHEM, "*.schem")))

    def render_path(path):
        name = os.path.splitext(os.path.basename(path))[0]
        image = render_cells_visible_iso(
            decode_schem_cells(path),
            tile_w=ROAD_ASSET_ISO_TILE_W,
            tile_h=ROAD_ASSET_ISO_TILE_H,
            block_h=ROAD_ASSET_ISO_BLOCK_H,
        )
        return name, image

    return render_contact_sheet(
        paths,
        output_dir=ROADS_RENDERS,
        contact_sheet=ROADS_CONTACT_SHEET,
        render_item=render_path,
        cols=5,
        cell_w=220,
        cell_h=190,
        contact_progress_label="Rendering road contact sheet...",
        contact_done_label="Rendered road contact sheet.",
        logger=logger,
        progress=progress,
        item_label="roads",
    )


if __name__ == "__main__":
    run_stage_cli(run)
