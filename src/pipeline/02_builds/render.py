"""Prod pipeline: render one isometric PNG per catalog build schematic, and their contact sheet."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.path import BUILD_CATALOG, BUILDS_CONTACT_SHEET, BUILDS_RENDERS, BUILDS_SCHEM
from engine.render.isometric import render_cells_visible_iso
from engine.schematic.building import assemble, read_catalog
from pipeline.rendering import render_contact_sheet
from pipeline.step import run_stage_cli

def run(*, logger=None, progress=None):
    """Render every build, then their contact sheet."""
    catalog = read_catalog(BUILD_CATALOG)

    def render_key(key):
        return key, render_cells_visible_iso(assemble(BUILDS_SCHEM, key, 1, catalog).cells)

    return render_contact_sheet(
        sorted(catalog),
        output_dir=BUILDS_RENDERS,
        contact_sheet=BUILDS_CONTACT_SHEET,
        render_item=render_key,
        cols=6,
        cell_w=200,
        cell_h=200,
        contact_progress_label="Rendering build contact sheet...",
        contact_done_label="Rendered build contact sheet.",
        logger=logger,
        progress=progress,
        item_label="builds",
    )

if __name__ == "__main__":
    run_stage_cli(run)
