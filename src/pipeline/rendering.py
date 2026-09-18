"""Shared helpers for rendering asset PNGs and contact sheets."""

from __future__ import annotations

import os

from PIL import Image, ImageSequence

from engine.render.contact_sheet import write_contact
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
    write_contact(
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


def write_image_sequence_gif(
    images,
    out,
    *,
    duration=500,
    loop=0,
):
    """Write image paths as a same-canvas animated GIF."""
    images = list(images)
    if not images:
        raise ValueError("cannot write a GIF with no images")

    frames = [Image.open(path).convert("RGBA") for path in images]
    try:
        max_w = max(frame.width for frame in frames)
        max_h = max(frame.height for frame in frames)
        prepared = []
        for frame in frames:
            canvas = Image.new("RGBA", (max_w, max_h), (255, 255, 255, 0))
            canvas.alpha_composite(frame, ((max_w - frame.width) // 2, (max_h - frame.height) // 2))
            prepared.append(canvas.convert("P", palette=Image.Palette.ADAPTIVE, colors=256))

        os.makedirs(os.path.dirname(out), exist_ok=True)
        prepared[0].save(
            out,
            save_all=True,
            append_images=prepared[1:],
            duration=duration,
            loop=loop,
            disposal=2,
            optimize=False,
        )
    finally:
        for frame in frames:
            frame.close()

    with Image.open(out) as gif:
        frame_count = sum(1 for _frame in ImageSequence.Iterator(gif))
        width, height = gif.size
    return {"path": out, "count": frame_count, "width": width, "height": height, "duration": duration}
