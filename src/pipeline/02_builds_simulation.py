"""Sim pipeline: draw pseudo top-down building PNG assets."""

from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.config_path import BUILD_CATALOG, BUILDS_SIM
from config.config_render import BUILD_PREVIEW_COLORS, CONTACT_SHEET_BG
from engine.city_layout import catalog_type
from pipeline.stages import noop, run_stage_cli

CATALOG = BUILD_CATALOG


def _clamp(v):
    return max(0, min(255, int(v)))


def shade(rgb, delta):
    return tuple(_clamp(c + delta) for c in rgb)


def font(size):
    for name in ("arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _rect(draw, box, fill, outline=None, width=1):
    x0, y0, x1, y1 = box
    if x1 < x0 or y1 < y0:
        return
    draw.rectangle([x0, y0, x1, y1], fill=fill, outline=outline, width=width)


def _subrects(rng, w, d, inset):
    inner_w = max(1, w - inset * 2)
    inner_d = max(1, d - inset * 2)
    n = 1 + min(4, max(w, d) // 18)
    rects = []
    for _ in range(n):
        rw = rng.randint(max(3, inner_w // 5), max(3, inner_w // 2))
        rd = rng.randint(max(3, inner_d // 5), max(3, inner_d // 2))
        rx = rng.randint(inset, max(inset, w - inset - rw))
        ry = rng.randint(inset, max(inset, d - inset - rd))
        rects.append((rx, ry, rx + rw - 1, ry + rd - 1))
    return rects


def render_building(key, meta):
    w, d = meta["size"]
    building_type = catalog_type(meta)
    rng = random.Random(int(key) * 104729 + building_type * 7919 + w * 37 + d)
    colors = BUILD_PREVIEW_COLORS[building_type]

    img = Image.new("RGBA", (w, d))
    draw = ImageDraw.Draw(img)
    inset = max(1, min(w, d) // 9)
    border = shade(colors["wall"], -45)

    _rect(draw, (0, 0, w - 1, d - 1), shade(colors["wall"], rng.randint(-10, 12)), border)
    _rect(
        draw,
        (inset, inset, w - inset - 1, d - inset - 1),
        shade(colors["roof"], rng.randint(-10, 12)),
        shade(colors["line"], 8),
    )

    if building_type == 1:
        ridge_y = d // 2 + rng.randint(-max(1, d // 12), max(1, d // 12))
        draw.line([(inset, ridge_y), (w - inset - 1, ridge_y)], fill=shade(colors["roof_alt"], 20), width=1)
        for box in _subrects(rng, w, d, inset + 1):
            _rect(draw, box, shade(colors["roof_alt"], rng.randint(-14, 10)), shade(colors["line"], 12))
    else:
        step = max(5, min(w, d) // 4)
        for x in range(inset + step // 2, w - inset, step):
            draw.line([(x, inset), (x, d - inset - 1)], fill=shade(colors["line"], 18))
        for y in range(inset + step // 2, d - inset, step):
            draw.line([(inset, y), (w - inset - 1, y)], fill=shade(colors["line"], 18))
        for box in _subrects(rng, w, d, inset + 1):
            _rect(draw, box, shade(colors["roof_alt"], rng.randint(-6, 16)), shade(colors["line"], 24))

    front_h = max(1, min(4, d // 5))
    _rect(draw, (1, d - front_h - 1, w - 2, d - 2), colors["front"])
    door_w = max(1, min(5, w // 4))
    door_x = max(1, (w - door_w) // 2)
    _rect(draw, (door_x, d - front_h - 1, door_x + door_w - 1, d - 2), shade(colors["glass"], 10))

    return img


def write_contact(images):
    cols, cw, ch, pad = 8, 180, 150, 8
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cw, rows * ch), CONTACT_SHEET_BG)
    d = ImageDraw.Draw(sheet)
    label_font = font(13)
    for i, (key, im) in enumerate(images):
        r, c = divmod(i, cols)
        x0, y0 = c * cw, r * ch
        scale = min((cw - pad * 2) / im.width, (ch - 28) / im.height, 6.0)
        thumb = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.Resampling.NEAREST)
        sheet.alpha_composite(thumb, (x0 + (cw - thumb.width) // 2, y0 + ch - thumb.height - 6))
        d.text((x0 + 6, y0 + 5), key, fill=(235, 235, 235, 255), font=label_font)
    out = os.path.join(BUILDS_SIM, "_contact_sheet.png")
    sheet.save(out)
    return out


def run(*, key=None, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop
    catalog = json.load(open(CATALOG))
    keys = [key] if key else sorted(catalog)
    os.makedirs(BUILDS_SIM, exist_ok=True)

    images = []
    total = len(keys)
    for index, build_key in enumerate(keys, start=1):
        if build_key not in catalog:
            raise SystemExit(f"unknown build key: {build_key}")
        im = render_building(build_key, catalog[build_key])
        out = os.path.join(BUILDS_SIM, f"{build_key}.png")
        im.save(out)
        images.append((build_key, im))
        logger(f"saved {out} ({im.width}x{im.height})")
        progress(index, total, build_key)

    contact = None
    if not key:
        contact = write_contact(images)
        logger(f"rendered {len(images)} pseudo builds -> {contact}")
    return {"count": len(images), "contact_sheet": contact}


if __name__ == "__main__":
    run_stage_cli(run, "key")
