"""Shared helpers for rendering asset PNGs and contact sheets."""

from __future__ import annotations

import os

from engine.render.isometric import write_contact as _write_contact
from pipeline.stages import noop


def render_contact_sheet(
    items,
    *,
    output_dir,
    render_item,
    cols,
    cell_w,
    cell_h,
    contact_name="_contact_sheet.png",
    contact_progress_label="Rendering contact sheet...",
    contact_done_label="Rendered contact sheet.",
    logger=None,
    progress=None,
    item_label="items",
    contact_writer=None,
):
    """Render ``items`` to PNG files, then assemble their contact sheet."""
    logger = logger or noop
    progress = progress or noop
    os.makedirs(output_dir, exist_ok=True)

    items = list(items)
    images = []
    total = len(items) * 2 + 1
    for index, item in enumerate(items, start=1):
        name, image = render_item(item)
        out = os.path.join(output_dir, f"{name}.png")
        image.save(out)
        images.append((name, out))
        logger(f"saved {out} ({image.width}x{image.height})")
        progress(index, total, name)

    contact = os.path.join(output_dir, contact_name)
    writer = contact_writer or _write_contact
    writer(
        images,
        contact,
        cols=cols,
        cell_w=cell_w,
        cell_h=cell_h,
        on_progress=lambda done, _contact_total: progress(
            len(items) + done,
            total,
            contact_done_label if done == len(images) + 1 else contact_progress_label,
        ),
    )
    logger(f"rendered {len(images)} {item_label} -> {contact}")
    return {"count": len(images), "contact_sheet": contact}
