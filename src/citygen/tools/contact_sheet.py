"""Contact sheets: a labelled grid of rendered asset thumbnails, and the label font every PNG renderer uses."""

from __future__ import annotations

import os
from contextlib import nullcontext
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

# Contact sheets are transparent, so they sit on whatever shows them (the app's sky canvas). Their labels are dark
# with a white outline, readable on a light background or a dark one.
CONTACT_SHEET_BG = (0, 0, 0, 0)
CONTACT_SHEET_LABEL = (42, 34, 26, 255)
CONTACT_SHEET_LABEL_OUTLINE = (255, 255, 255, 255)


@lru_cache(maxsize=None)
def label_font(size):
    """Bold Arial when available, then Arial, then Pillow's built-in font."""
    for name in ("arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


THUMB_PAD = 8  # horizontal clearance between a thumbnail and its cell edge


def _open_contact_source(image_source):
    if isinstance(image_source, (str, bytes, os.PathLike)):
        return Image.open(image_source)
    return nullcontext(image_source)


def write_contact(images, out, cols=8, cell_w=180, cell_h=180, on_progress=None):
    """Grid ``(label, image-or-path)`` pairs onto one sheet and save it to ``out``; thumbnails shrink to fit."""
    rows = max(1, (len(images) + cols - 1) // cols)
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), CONTACT_SHEET_BG)
    d = ImageDraw.Draw(sheet)
    font = label_font(13)
    for i, (key, im) in enumerate(images):
        r, c = divmod(i, cols)
        x0, y0 = c * cell_w, r * cell_h
        with _open_contact_source(im) as source:
            source_rgba = source if source.mode == "RGBA" else source.convert("RGBA")
            scale = min((cell_w - THUMB_PAD * 2) / source_rgba.width, (cell_h - 28) / source_rgba.height, 1.0)
            thumb = source_rgba.resize(
                (max(1, int(source_rgba.width * scale)), max(1, int(source_rgba.height * scale))),
                Image.Resampling.LANCZOS,
            )
        sheet.alpha_composite(thumb, (x0 + (cell_w - thumb.width) // 2,
                                      y0 + cell_h - thumb.height - 6))
        d.text((x0 + 6, y0 + 5), key, fill=CONTACT_SHEET_LABEL, font=font,
               stroke_width=2, stroke_fill=CONTACT_SHEET_LABEL_OUTLINE)
        if on_progress is not None:
            on_progress(i + 1, len(images) + 1)
    sheet.save(out)
    if on_progress is not None:
        on_progress(len(images) + 1, len(images) + 1)
    return sheet


def render_contact_sheet(items, render_item, output_dir, contact_sheet, progress):
    """Render each item to ``<name>.png`` in ``output_dir``, then their contact sheet.

    ``render_item(item)`` returns ``(name, image)``. ``progress(completed, total, detail)`` names each piece once its PNG
    is saved, so the app can show it as it lands.
    """
    os.makedirs(output_dir, exist_ok=True)
    items = list(items)
    images = []
    total = len(items) * 2 + 1
    progress(0, total, None)   # before the first (slowest) item, so the bar shows movement
    for index, item in enumerate(items, start=1):
        name, image = render_item(item)
        out = os.path.join(output_dir, f"{name}.png")
        image.save(out)
        images.append((name, out))
        progress(index, total, name)
    write_contact(
        images, contact_sheet, cols=6, cell_w=200, cell_h=200,
        on_progress=lambda done, _total: progress(len(items) + done, total, None),
    )
