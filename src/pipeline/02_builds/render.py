"""Prod pipeline: render one isometric PNG per catalog build schematic."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.path import BUILD_CATALOG, BUILDS_CONTACT_SHEET, BUILDS_GIF, BUILDS_RENDERS, BUILDS_SCHEM
from engine.render.isometric import render_cells_visible_iso
from engine.schematic.building import assemble, read_catalog
from pipeline.rendering import render_contact_sheet, write_image_sequence_gif
from pipeline.stages import noop, run_stage_cli

def run(*, logger=None, progress=None):
    """Render every build and its contact sheet, then the showcase GIF.

    Progress spans both parts, so the step only reports completion once the
    GIF is written.
    """
    logger = logger or noop
    progress = progress or noop
    catalog = read_catalog(BUILD_CATALOG)
    keys = sorted(catalog)
    gif_steps = len(keys) + 1
    sheet_steps = 0

    def render_key(key):
        return key, render_cells_visible_iso(assemble(BUILDS_SCHEM, key, 1, catalog).cells)

    def sheet_progress(done, total, label):
        nonlocal sheet_steps
        sheet_steps = total
        progress(done, total + gif_steps, label)

    def gif_progress(done, _total):
        label = "Rendered building GIF." if done == gif_steps else "Rendering building GIF..."
        progress(sheet_steps + done, sheet_steps + gif_steps, label)

    result = render_contact_sheet(
        keys,
        output_dir=BUILDS_RENDERS,
        contact_sheet=BUILDS_CONTACT_SHEET,
        render_item=render_key,
        cols=8,
        cell_w=180,
        cell_h=180,
        contact_progress_label="Rendering build contact sheet...",
        contact_done_label="Rendered build contact sheet.",
        logger=logger,
        progress=sheet_progress,
        item_label="builds",
    )
    gif_sources = [os.path.join(BUILDS_RENDERS, f"{key}.png") for key in reversed(keys)]
    result["gif"] = write_image_sequence_gif(gif_sources, BUILDS_GIF, duration=500, on_progress=gif_progress)
    logger(f"rendered building GIF -> {result['gif']} ({len(gif_sources)} frames)")
    return result


if __name__ == "__main__":
    run_stage_cli(run)
