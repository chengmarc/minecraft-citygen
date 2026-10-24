"""Shared helpers for rendering asset PNGs and contact sheets."""

from __future__ import annotations

import os

from engine.render.contact_sheet import write_contact
from pipeline.step import noop


def render_contact_sheet(
    items,
    *,
    output_dir,
    contact_sheet,
    render_item,
    cols,
    cell_w,
    cell_h,
    contact_progress_label="Rendering contact sheet...",
    contact_done_label="Rendered contact sheet.",
    logger=None,
    progress=None,
    item_label="items",
):
    """Render ``items`` to PNG files, then assemble their contact sheet."""
    logger = logger or noop
    progress = progress or noop
    os.makedirs(output_dir, exist_ok=True)

    items = list(items)
    images = []
    total = len(items) * 2 + 1
    # Announce before the first (slowest) item so callers can show movement.
    progress(0, total, f"Rendering {item_label}...")
    for index, item in enumerate(items, start=1):
        name, image = render_item(item)
        out = os.path.join(output_dir, f"{name}.png")
        image.save(out)
        images.append((name, out))
        logger(f"saved {out} ({image.width}x{image.height})")
        progress(index, total, name)

    write_contact(
        images,
        contact_sheet,
        cols=cols,
        cell_w=cell_w,
        cell_h=cell_h,
        on_progress=lambda done, _contact_total: progress(
            len(items) + done,
            total,
            contact_done_label if done == len(images) + 1 else contact_progress_label,
        ),
    )
    logger(f"rendered {len(images)} {item_label} -> {contact_sheet}")
    return {"count": len(images), "contact_sheet": contact_sheet}

