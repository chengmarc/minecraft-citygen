"""The Preview tab's run: flat top-down stand-ins for the road pieces and buildings, laid out as the seed's road
layout and city layout.

Nothing is built in blocks, so it's fast; but the layout comes from the same ``plan_city`` as the build, so what you
preview is what gets built.
"""

from __future__ import annotations

import os
import random

from PIL import Image, ImageDraw

from citygen.city_layout import FACE_K, FILLER_STREAM, placement_origin, plan_city, seeded_rng
from citygen.contact_sheet import label_font
from citygen.paths import BUILD_CATALOG, city_preview_path, grid_preview_path
from citygen.road_network import gen_networks, iter_placements, iter_tile_catalogue, make_size, tile_footprint
from citygen.schem import read_catalog
from citygen.settings import CELL

CITY_GROUND_FILL_RGBA = (159, 159, 159, 255)


def run(seed, algo, progress):
    """Write the road layout and the city layout of ``seed`` under ``algo``.

    ``progress(step, completed, total)`` reports each step by its code: ``road_pieces``, ``build_pieces``,
    ``road_layout``, ``city_layout``. The road layout is saved before the city layout is started.
    """
    road_tiles = draw_road_tiles(lambda completed, total: progress("road_pieces", completed, total))
    catalog = read_catalog(BUILD_CATALOG)
    building_tiles = draw_building_tiles(catalog, lambda completed, total: progress("build_pieces", completed, total))

    progress("road_layout", 0, 1)
    net = gen_networks(seed, make_size(algo.fine), algo)
    roads = compose(net, road_tiles)
    save(roads, grid_preview_path(seed))
    progress("road_layout", 1, 1)

    progress("city_layout", 0, 2)
    _lots, placements = plan_city(seed, net, catalog, algo)
    progress("city_layout", 1, 2)
    fillers = [road_tiles[name] for name in FILL_TILES]
    city = render_city(net, roads, placements, building_tiles, fillers, seeded_rng(seed, FILLER_STREAM))
    save(city, city_preview_path(seed))
    progress("city_layout", 2, 2)


def save(image, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    image.save(path)


def rot_img(img, k):
    for _ in range(k % 4):
        img = img.transpose(Image.Transpose.ROTATE_270)  # 90 deg clockwise
    return img


def compose(net, assets):
    size = net["size"]
    canvas = Image.new("RGBA", (size.span, size.span))
    for placement in iter_placements(net):
        img = rot_img(assets[placement.tile_name], placement.rotation)
        canvas.alpha_composite(img, (placement.fx * CELL, placement.fy * CELL))
    return canvas


# --- The road pieces, drawn top-down
#
# Cell size        : 9 px
# Footprints       : 1x1 -> 9x9, 1x2 -> 9x18, 2x2 -> 18x18
# Small road width : 7 px  (1 px padding, white centerline)
# Big road width   : 14 px (2 px padding, yellow lane divider)
#
# A tile is described by which of the 4 edges (N/E/S/W) it connects to,
# and the road *size* of each connection ("s" = small, "b" = big).
# Roads run along the cell centerline so equal road types align when
# tiles are placed next to each other.

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
DASH = 4
GAP = 3


def line_span(center, width):
    if width % 2:
        half = width // 2
        return center - half, center + half
    return center - width // 2, center + width // 2 - 1


def dashed(draw, p0, p1, color, width):
    (x0, y0), (x1, y1) = p0, p1
    if x0 == x1:
        lo, hi = line_span(x0, width)
        step = 1 if y1 >= y0 else -1
        d = 0
        total = abs(y1 - y0)
        while d <= total:
            seg = min(DASH - 1, total - d)
            ya = y0 + step * d
            yb = y0 + step * (d + seg)
            draw.rectangle([lo, min(ya, yb), hi, max(ya, yb)], fill=color)
            d += DASH + GAP
        return
    if y0 == y1:
        lo, hi = line_span(y0, width)
        step = 1 if x1 >= x0 else -1
        d = 0
        total = abs(x1 - x0)
        while d <= total:
            seg = min(DASH - 1, total - d)
            xa = x0 + step * d
            xb = x0 + step * (d + seg)
            draw.rectangle([min(xa, xb), lo, max(xa, xb), hi], fill=color)
            d += DASH + GAP
        return

    dx, dy = x1 - x0, y1 - y0
    length = (dx * dx + dy * dy) ** 0.5
    if length == 0:
        return
    ux, uy = dx / length, dy / length
    d = 0.0
    while d < length:
        seg = min(DASH, length - d)
        a = (x0 + ux * d, y0 + uy * d)
        b = (x0 + ux * (d + seg), y0 + uy * (d + seg))
        draw.line([a, b], fill=color, width=width, joint="curve")
        d += DASH + GAP


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


EDGE_DRAW_ORDER = "NSEW"  # make_tile overdraws, so edge order changes mixed-tile pixels

# One top-down tile per road-network catalogue entry, drawn in its base
# orientation: (width_px, height_px, {edge: size}).
TILES = {
    name: (cols * CELL, rows * CELL, dict(sorted(base, key=lambda port: EDGE_DRAW_ORDER.index(port[0]))))
    for layer, base, name in sorted(iter_tile_catalogue(), key=lambda entry: entry[2])
    for cols, rows in [tile_footprint(layer, base)]
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


def draw_road_tiles(progress):
    """Every road piece and fill prop, by name."""
    tiles = {}
    total = len(TILES) + len(FILL_TILES)
    for name, (w, h, conns) in TILES.items():
        tiles[name] = make_tile(w, h, conns)
        progress(len(tiles), total)
    for name, canopy in FILL_TILES.items():
        tiles[name] = make_fill_tile(canopy)
        progress(len(tiles), total)
    return tiles


# --- The buildings, drawn top-down

BUILD_PREVIEW_COLORS = {
    1: {
        "wall": (185, 156, 108),
        "roof": (126, 65, 48),
        "roof_alt": (156, 88, 58),
        "line": (92, 55, 42),
        "front": (47, 39, 34),
        "glass": (93, 130, 150),
    },
    2: {
        "wall": (150, 158, 166),
        "roof": (76, 86, 96),
        "roof_alt": (102, 115, 126),
        "line": (45, 53, 62),
        "front": (30, 34, 39),
        "glass": (84, 152, 178),
    },
}


def _clamp(v):
    return max(0, min(255, int(v)))


def shade(rgb, delta):
    return tuple(_clamp(c + delta) for c in rgb)


def _rect(draw, box, fill, outline=None):
    x0, y0, x1, y1 = box
    if x1 < x0 or y1 < y0:
        return
    draw.rectangle([x0, y0, x1, y1], fill=fill, outline=outline)


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
    building_type = meta["type"]
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


def draw_building_tiles(catalog, progress):
    """Every building in the catalog, by key."""
    tiles = {}
    for key in sorted(catalog):
        tiles[key] = render_building(key, catalog[key])
        progress(len(tiles), len(catalog))
    return tiles


# --- The layouts


def paste_building(canvas, asset, key, facing, rect):
    t = rot_img(asset, FACE_K[facing])
    px, py = placement_origin(rect, facing, t.width, t.height)
    canvas.alpha_composite(t, (px, py))
    draw_label(canvas, key, px, py, t.width, t.height)


def draw_label(canvas, key, x, y, w, h):
    if w < 8 or h < 8:
        return
    draw = ImageDraw.Draw(canvas)
    size = max(5, min(13, int(min(w / max(1, len(key) * 0.55), h * 0.55))))
    font = label_font(size)
    bbox = draw.textbbox((0, 0), key, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cx, cy = x + w // 2, y + h // 2
    pad_x, pad_y = 2, 1
    draw.rectangle(
        [cx - tw // 2 - pad_x, cy - th // 2 - pad_y, cx + tw // 2 + pad_x, cy + th // 2 + pad_y],
        fill=(20, 22, 24, 210),
    )
    draw.text((cx, cy), key, fill=(245, 240, 220, 255), font=font, anchor="mm")


def fill_lots(road_cells, size):
    canvas = Image.new("RGBA", (size.span, size.span))
    draw = ImageDraw.Draw(canvas)
    for fy in range(size.fine):
        for fx in range(size.fine):
            if (fx, fy) in road_cells:
                continue
            x0, y0 = fx * CELL, fy * CELL
            x1, y1 = x0 + CELL - 1, y0 + CELL - 1
            draw.rectangle([x0, y0, x1, y1], fill=CITY_GROUND_FILL_RGBA)
    return canvas


def place_fill_props(canvas, road_cells, occupied, size, fillers, rng):
    """Paste a random fill prop into every empty non-road, non-building cell.

    Mirrors production: building cells are skipped (a building sits there), the
    same seeded RNG order is used so the preview matches the built city.
    """
    for fy in range(size.fine):
        for fx in range(size.fine):
            if (fx, fy) in road_cells or (fx, fy) in occupied:
                continue
            tile = rot_img(rng.choice(fillers), rng.randint(0, 3))
            canvas.alpha_composite(tile, (fx * CELL, fy * CELL))


def render_city(net, roads, placements, building_tiles, fillers, rng):
    """Lot ground and fill props, the ``roads`` over them, then each placed building with its key."""
    canvas = fill_lots(net["road_cells"], net["size"])
    occupied = {cell for placement in placements for cell in placement.rect.cells()}
    place_fill_props(canvas, net["road_cells"], occupied, net["size"], fillers, rng)
    canvas.alpha_composite(roads)
    for placement in placements:
        key = placement.building.num
        paste_building(canvas, building_tiles[key], key, placement.facing, placement.rect)
    return canvas
