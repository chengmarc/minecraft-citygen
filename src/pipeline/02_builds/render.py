"""Prod pipeline: render one isometric PNG per catalog build schematic."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.path import BUILD_CATALOG, BUILDS_RENDERS, BUILDS_SCHEM
from engine.render.isometric import render_cells_visible_iso, write_contact
from engine.schematic.reader import decode_schem_cells
from pipeline.rendering import render_contact_sheet
from pipeline.stages import run_stage_cli

SCHEM = BUILDS_SCHEM
CATALOG = BUILD_CATALOG


def assemble(key, meta):
    pieces = meta.get("pieces", {})
    if "whole" in pieces:
        return decode_schem_cells(os.path.join(SCHEM, f"{key}.schem"))
    cells = []
    for part in ("bottom", "middle", "top"):
        cells.extend(decode_schem_cells(os.path.join(SCHEM, f"{key}_{part}.schem")))
    return cells


def run(*, logger=None, progress=None):
    with open(CATALOG, encoding="utf-8") as fh:
        catalog = json.load(fh)

    keys = sorted(catalog)

    def render_key(key):
        return key, render_cells_visible_iso(assemble(key, catalog[key]))

    return render_contact_sheet(
        keys,
        output_dir=BUILDS_RENDERS,
        render_item=render_key,
        cols=8,
        cell_w=180,
        cell_h=180,
        contact_progress_label="Rendering build contact sheet...",
        contact_done_label="Rendered build contact sheet.",
        logger=logger,
        progress=progress,
        item_label="builds",
        contact_writer=write_contact,
    )


if __name__ == "__main__":
    run_stage_cli(run)
