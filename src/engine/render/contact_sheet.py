"""Labelled contact-sheet grids of rendered asset thumbnails."""

from __future__ import annotations

import os
from contextlib import nullcontext

from PIL import Image, ImageDraw

from config.render import CONTACT_SHEET_BG
from engine.render.fonts import label_font

THUMB_PAD = 8  # horizontal clearance between a thumbnail and its cell edge


def _open_contact_source(image_source):
    if isinstance(image_source, (str, bytes, os.PathLike)):
        return Image.open(image_source)
    return nullcontext(image_source)


def write_contact(
    images,
    out,
    cols=8,
    cell_w=180,
    cell_h=180,
    on_progress=None,
    *,
    max_scale=1.0,
    resample=Image.Resampling.LANCZOS,
):
    """Grid ``(label, image-or-path)`` pairs onto one sheet and save it to ``out``.

    Thumbnails shrink to fit their cell, and grow up to ``max_scale`` (pixel-art
    previews pass a larger scale with NEAREST resampling).
    """
    rows = max(1, (len(images) + cols - 1) // cols)
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), CONTACT_SHEET_BG)
    d = ImageDraw.Draw(sheet)
    font = label_font(13)
    for i, (key, im) in enumerate(images):
        r, c = divmod(i, cols)
        x0, y0 = c * cell_w, r * cell_h
        with _open_contact_source(im) as source:
            source_rgba = source if source.mode == "RGBA" else source.convert("RGBA")
            scale = min((cell_w - THUMB_PAD * 2) / source_rgba.width, (cell_h - 28) / source_rgba.height, max_scale)
            thumb = source_rgba.resize(
                (max(1, int(source_rgba.width * scale)), max(1, int(source_rgba.height * scale))),
                resample,
            )
        sheet.alpha_composite(thumb, (x0 + (cell_w - thumb.width) // 2,
                                      y0 + cell_h - thumb.height - 6))
        d.text((x0 + 6, y0 + 5), key, fill=(235, 235, 235, 255), font=font)
        if on_progress is not None:
            on_progress(i + 1, len(images) + 1)
    sheet.save(out)
    if on_progress is not None:
        on_progress(len(images) + 1, len(images) + 1)
    return sheet
