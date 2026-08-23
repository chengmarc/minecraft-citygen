"""Prod pipeline: render one isometric PNG per catalog build schematic."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.config_path import BUILD_CATALOG, BUILDS_PROD
from engine.core.city_layout import catalog_type
from engine.render.isometric import render_cells_visible_iso, write_contact
from engine.schematic.reader import decode_schem_cells
from pipeline.stages import noop, run_stage_cli

SCHEM = BUILDS_PROD
CATALOG = BUILD_CATALOG


def assemble(key, meta):
    if catalog_type(meta) == 1:
        return decode_schem_cells(os.path.join(SCHEM, f"{key}.schem"))
    cells = []
    for part in ("bottom", "middle", "top"):
        cells.extend(decode_schem_cells(os.path.join(SCHEM, f"{key}_{part}.schem")))
    return cells


def run(*, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop
    catalog = json.load(open(CATALOG))
    os.makedirs(BUILDS_PROD, exist_ok=True)

    images = []
    keys = sorted(catalog)
    total = len(keys)
    for index, key in enumerate(keys, start=1):
        im = render_cells_visible_iso(assemble(key, catalog[key]))
        out = os.path.join(BUILDS_PROD, f"{key}.png")
        im.save(out)
        images.append((key, im))
        logger(f"saved {out} ({im.width}x{im.height})")
        progress(index, total, key)

    contact = os.path.join(BUILDS_PROD, "_contact_sheet.png")
    progress(0, 1, "Rendering build contact sheet...")
    write_contact(images, contact, cols=8, cell_w=180, cell_h=180)
    progress(1, 1, "Rendered build contact sheet.")
    logger(f"rendered {len(images)} builds -> {contact}")
    return {"count": len(images), "contact_sheet": contact}


if __name__ == "__main__":
    run_stage_cli(run)
