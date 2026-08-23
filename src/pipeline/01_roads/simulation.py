"""
Road grid tile generator (step 1: schematic PNG assets).

Conventions
-----------
Cell size        : 9 px
Footprints       : 1x1 -> 9x9, 1x2 -> 9x18, 2x2 -> 18x18
Small road width : 7 px  (1 px padding, white centerline)
Big road width   : 14 px (2 px padding, yellow lane divider)

A tile is described by which of the 4 edges (N/E/S/W) it connects to,
and the road *size* of each connection ("s" = small, "b" = big).
Roads run along the cell centerline so equal road types align when
tiles are placed next to each other.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.config_algo import CELL
from config.config_path import ROADS_SIM
from config.config_render import CITY_GROUND_FILL_RGBA
from pipeline.stages import noop, run_stage_cli

SMALL_PAD = 1
BIG_PAD = 2
SMALL_W = CELL - SMALL_PAD * 2
BIG_W = CELL * 2 - BIG_PAD * 2

ROAD = (72, 74, 80)
YELLOW = (245, 205, 45)
WHITE = (235, 235, 235)

WIDTH = {"s": SMALL_W, "b": BIG_W}
LINE = {"s": WHITE, "b": YELLOW}
LINE_W = {"s": 1, "b": 2}
DEADEND_EXT = 2
DEADEND_PAD = 1

OUT = ROADS_SIM


def line_span(center, width):
    if width % 2:
        half = width // 2
        return center - half, center + half
    return center - width // 2, center + width // 2 - 1


def dashed(draw, p0, p1, color, width, dash=4, gap=3):
    (x0, y0), (x1, y1) = p0, p1
    if x0 == x1:
        lo, hi = line_span(x0, width)
        step = 1 if y1 >= y0 else -1
        d = 0
        total = abs(y1 - y0)
        while d <= total:
            seg = min(dash - 1, total - d)
            ya = y0 + step * d
            yb = y0 + step * (d + seg)
            draw.rectangle([lo, min(ya, yb), hi, max(ya, yb)], fill=color)
            d += dash + gap
        return
    if y0 == y1:
        lo, hi = line_span(y0, width)
        step = 1 if x1 >= x0 else -1
        d = 0
        total = abs(x1 - x0)
        while d <= total:
            seg = min(dash - 1, total - d)
            xa = x0 + step * d
            xb = x0 + step * (d + seg)
            draw.rectangle([min(xa, xb), lo, max(xa, xb), hi], fill=color)
            d += dash + gap
        return

    dx, dy = x1 - x0, y1 - y0
    length = (dx * dx + dy * dy) ** 0.5
    if length == 0:
        return
    ux, uy = dx / length, dy / length
    d = 0.0
    while d < length:
        seg = min(dash, length - d)
        a = (x0 + ux * d, y0 + uy * d)
        b = (x0 + ux * (d + seg), y0 + uy * (d + seg))
        draw.line([a, b], fill=color, width=width, joint="curve")
        d += dash + gap


def span(center, width):
    lo = center - width // 2
    hi = lo + width - 1
    return lo, hi


def make_tile(w, h, conns):
    """conns: dict edge -> size, edge in {N,E,S,W}, size in {s,b}."""
    img = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2

    for edge, size in conns.items():
        rw = WIDTH[size]
        x0, x1 = span(cx, rw)
        y0, y1 = span(cy, rw)
        if edge == "N":
            d.rectangle([x0, 0, x1, cy], fill=ROAD)
        elif edge == "S":
            d.rectangle([x0, cy, x1, h], fill=ROAD)
        elif edge == "W":
            d.rectangle([0, y0, cx, y1], fill=ROAD)
        elif edge == "E":
            d.rectangle([cx, y0, w, y1], fill=ROAD)

    ns = [WIDTH[s] for e, s in conns.items() if e in ("N", "S")]
    ew = [WIDTH[s] for e, s in conns.items() if e in ("E", "W")]
    if ns and ew:
        x0, x1 = span(cx, max(ns))
        y0, y1 = span(cy, max(ew))
        d.rectangle([x0, y0, x1, y1], fill=ROAD)

    if len(conns) == 1:
        edge, size = next(iter(conns.items()))
        rw = WIDTH[size]
        x0, x1 = span(cx, rw)
        y0, y1 = span(cy, rw)
        if edge == "S":
            d.rectangle([x0, DEADEND_PAD, x1, h - 1], fill=ROAD)
        elif edge == "N":
            d.rectangle([x0, 0, x1, h - DEADEND_PAD - 1], fill=ROAD)
        elif edge == "E":
            d.rectangle([DEADEND_PAD, y0, w - 1, y1], fill=ROAD)
        elif edge == "W":
            d.rectangle([0, y0, w - DEADEND_PAD - 1, y1], fill=ROAD)

    for edge, size in conns.items():
        col = LINE[size]
        lw = LINE_W[size]
        if len(conns) == 1 and edge == "S":
            dashed(d, (cx, DEADEND_PAD + DEADEND_EXT), (cx, h - 1), col, lw)
        elif len(conns) == 1 and edge == "N":
            dashed(d, (cx, h - DEADEND_PAD - DEADEND_EXT - 1), (cx, 0), col, lw)
        elif len(conns) == 1 and edge == "E":
            dashed(d, (DEADEND_PAD + DEADEND_EXT, cy), (w - 1, cy), col, lw)
        elif len(conns) == 1 and edge == "W":
            dashed(d, (w - DEADEND_PAD - DEADEND_EXT - 1, cy), (0, cy), col, lw)
        elif edge == "N":
            dashed(d, (cx, cy), (cx, 0), col, lw)
        elif edge == "S":
            dashed(d, (cx, cy), (cx, h), col, lw)
        elif edge == "W":
            dashed(d, (cx, cy), (0, cy), col, lw)
        elif edge == "E":
            dashed(d, (cx, cy), (w, cy), col, lw)

    if len(conns) == 1:
        edge, size = next(iter(conns.items()))
        rw = WIDTH[size]
        x0, x1 = span(cx, rw)
        y0, y1 = span(cy, rw)
        if edge == "S":
            d.rectangle([x0, DEADEND_PAD, x1, DEADEND_PAD + DEADEND_EXT - 1], fill=(200, 200, 200))
        elif edge == "N":
            d.rectangle([x0, h - DEADEND_PAD - DEADEND_EXT, x1, h - DEADEND_PAD - 1], fill=(200, 200, 200))
        elif edge == "E":
            d.rectangle([DEADEND_PAD, y0, DEADEND_PAD + DEADEND_EXT - 1, y1], fill=(200, 200, 200))
        elif edge == "W":
            d.rectangle([w - DEADEND_PAD - DEADEND_EXT, y0, w - DEADEND_PAD - 1, y1], fill=(200, 200, 200))
    return img


TILES = {
    "01_big_2x2_deadend": (CELL * 2, CELL * 2, {"S": "b"}),
    "02_big_2x2_I": (CELL * 2, CELL * 2, {"N": "b", "S": "b"}),
    "03_big_2x2_L": (CELL * 2, CELL * 2, {"N": "b", "E": "b"}),
    "04_big_2x2_T": (CELL * 2, CELL * 2, {"S": "b", "E": "b", "W": "b"}),
    "05_big_2x2_X": (CELL * 2, CELL * 2, {"N": "b", "S": "b", "E": "b", "W": "b"}),
    "06_small_1x1_deadend": (CELL, CELL, {"S": "s"}),
    "07_small_1x1_I": (CELL, CELL, {"N": "s", "S": "s"}),
    "08_small_1x1_L": (CELL, CELL, {"N": "s", "E": "s"}),
    "09_small_1x1_T": (CELL, CELL, {"S": "s", "E": "s", "W": "s"}),
    "10_small_1x1_X": (CELL, CELL, {"N": "s", "S": "s", "E": "s", "W": "s"}),
    "11_mix_1x2_L": (CELL * 2, CELL, {"N": "b", "E": "s"}),
    "12_mix_1x2_T_small_main": (CELL * 2, CELL, {"S": "b", "E": "s", "W": "s"}),
    "13_mix_1x2_T_big_main": (CELL, CELL * 2, {"S": "s", "E": "b", "W": "b"}),
    "14_mix_1x2_X": (CELL * 2, CELL, {"N": "b", "S": "b", "E": "s", "W": "s"}),
}


# Top-down fill props: a smooth-stone cell (matching the ground fill) with a
# tree drawn inside. Variants mirror the in-world species of the extracted fill
# schematics (15 = spruce, 16 = birch, 17 = oak).
FILL_TILES = {
    "15_fill_1x1_A": (46, 96, 52),     # spruce -- dark green
    "16_fill_1x1_B": (122, 165, 86),   # birch  -- light green
    "17_fill_1x1_C": (86, 130, 60),    # oak    -- mid green
}
TRUNK = (99, 71, 45)


def _shade(rgb, delta):
    return tuple(max(0, min(255, c + delta)) for c in rgb)


def make_fill_tile(canopy):
    """A 9x9 smooth-stone cell with a round top-down tree canopy in its centre."""
    img = Image.new("RGBA", (CELL, CELL))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, CELL - 1, CELL - 1], fill=CITY_GROUND_FILL_RGBA)
    cx, cy = CELL // 2, CELL // 2
    r = CELL // 2 - 1                       # leave a 1px smooth-stone border ring
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=canopy, outline=_shade(canopy, -34))
    d.point((cx - 1, cy - 1), fill=_shade(canopy, 28))   # highlight
    d.point((cx + 1, cy + 1), fill=_shade(canopy, -24))  # shadow
    d.point((cx, cy), fill=TRUNK)                          # trunk
    return img


def run(*, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop
    os.makedirs(OUT, exist_ok=True)
    imgs = {}
    total = len(TILES) + len(FILL_TILES)
    for index, (name, (w, h, conns)) in enumerate(TILES.items(), start=1):
        img = make_tile(w, h, conns)
        path = os.path.join(OUT, name + ".png")
        img.save(path)
        imgs[name] = img
        logger(f"saved {name}.png ({w}x{h})")
        progress(index, total, name)

    for offset, (name, canopy) in enumerate(FILL_TILES.items()):
        img = make_fill_tile(canopy)
        path = os.path.join(OUT, name + ".png")
        img.save(path)
        imgs[name] = img
        logger(f"saved {name}.png ({CELL}x{CELL})")
        progress(len(TILES) + offset + 1, total, name)

    cols = 5
    zoom = 8
    pad = 12
    label_h = 22
    cellw = CELL * 2 * zoom + pad
    cellh = CELL * 2 * zoom + label_h + pad
    rows = (len(TILES) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cellw + pad, rows * cellh + pad), (30, 30, 34, 255))
    sd = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    for i, (name, img) in enumerate(imgs.items()):
        r, c = divmod(i, cols)
        x = pad + c * cellw
        y = pad + r * cellh
        sd.text((x, y), name, fill=(230, 230, 230), font=font)
        preview = img.resize((img.width * zoom, img.height * zoom), Image.Resampling.NEAREST)
        sheet.alpha_composite(preview, (x, y + label_h))
    contact_sheet = os.path.join(OUT, "_contact_sheet.png")
    sheet.save(contact_sheet)
    logger("saved _contact_sheet.png")
    return {"count": total, "contact_sheet": contact_sheet}


if __name__ == "__main__":
    run_stage_cli(run)
