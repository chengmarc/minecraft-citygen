"""Shared PNG render helpers for schematic/block previews."""
import csv

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from config.config_path import COLOR_RENDER_CSV
from config.config_render import (CONTACT_SHEET_BG, ISO_MARGIN, ROAD_ASSET_ISO_BLOCK_H,
                                  ROAD_ASSET_ISO_TILE_H, ROAD_ASSET_ISO_TILE_W,
                                  UNKNOWN_BLOCK_RGBA)
from engine.schematic_reader import decode_schem_array

try:
    from numba import njit
except Exception:
    njit = None

TILE_W = ROAD_ASSET_ISO_TILE_W
TILE_H = ROAD_ASSET_ISO_TILE_H
BLOCK_H = ROAD_ASSET_ISO_BLOCK_H
MARGIN = ISO_MARGIN
UNKNOWN = UNKNOWN_BLOCK_RGBA


def _load_render_colors(path=COLOR_RENDER_CSV):
    colors = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            block = (row.get("block_name") or "").strip()
            r, g, b = ((row.get(k) or "").strip() for k in ("r", "g", "b"))
            if not block or not r or not g or not b:
                continue
            colors[block] = (int(r), int(g), int(b))
    return colors


COLORS = _load_render_colors()


def block_id(state):
    """Return a namespaced block id from a block state or base name."""
    name = str(state).split("[", 1)[0]
    return name if ":" in name else f"minecraft:{name}"


def is_air(state):
    return block_id(state) in {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}


def block_color(state, default=UNKNOWN):
    return COLORS.get(block_id(state), default)


def cells_to_grid(cells):
    palette = {"minecraft:air": 0}
    H, L, W = len(cells), len(cells[0]), len(cells[0][0])
    grid = np.zeros((H, L, W), dtype=np.int32)
    for y in range(H):
        for z in range(L):
            for x in range(W):
                state = cells[y][z][x]
                idx = palette.get(state)
                if idx is None:
                    idx = palette[state] = len(palette)
                grid[y, z, x] = idx
    inv = {v: k for k, v in palette.items()}
    return W, H, L, inv, grid


if njit is not None:
    @njit(cache=True)
    def _draw_triangle(img, depth, p0x, p0y, p0d, p1x, p1y, p1d, p2x, p2y, p2d, r, g, b):
        h, w, _ = img.shape
        min_x = max(0, int(np.floor(min(p0x, p1x, p2x))))
        max_x = min(w - 1, int(np.ceil(max(p0x, p1x, p2x))))
        min_y = max(0, int(np.floor(min(p0y, p1y, p2y))))
        max_y = min(h - 1, int(np.ceil(max(p0y, p1y, p2y))))
        den = (p1y - p2y) * (p0x - p2x) + (p2x - p1x) * (p0y - p2y)
        if den == 0.0:
            return
        for py_i in range(min_y, max_y + 1):
            py = py_i + 0.5
            for px_i in range(min_x, max_x + 1):
                px = px_i + 0.5
                a = ((p1y - p2y) * (px - p2x) + (p2x - p1x) * (py - p2y)) / den
                b0 = ((p2y - p0y) * (px - p2x) + (p0x - p2x) * (py - p2y)) / den
                c = 1.0 - a - b0
                if a >= -0.0001 and b0 >= -0.0001 and c >= -0.0001:
                    d = a * p0d + b0 * p1d + c * p2d
                    if d > depth[py_i, px_i]:
                        depth[py_i, px_i] = d
                        img[py_i, px_i, 0] = r
                        img[py_i, px_i, 1] = g
                        img[py_i, px_i, 2] = b
                        img[py_i, px_i, 3] = 255


    @njit(cache=True)
    def _draw_quad(img, depth, xs, ys, ds, r, g, b):
        _draw_triangle(img, depth, xs[0], ys[0], ds[0], xs[1], ys[1], ds[1],
                       xs[2], ys[2], ds[2], r, g, b)
        _draw_triangle(img, depth, xs[0], ys[0], ds[0], xs[2], ys[2], ds[2],
                       xs[3], ys[3], ds[3], r, g, b)


    @njit(cache=True)
    def _raster_visible_iso(grid, solid, colors, img, depth, tile_w, tile_h, block_h, ox, oy):
        H, L, W = grid.shape
        xs = np.empty(4, dtype=np.float32)
        ys = np.empty(4, dtype=np.float32)
        ds = np.empty(4, dtype=np.float32)
        for y in range(H):
            for z in range(L):
                for x in range(W):
                    idx = grid[y, z, x]
                    if not solid[idx]:
                        continue
                    r0 = colors[idx, 0]
                    g0 = colors[idx, 1]
                    b0 = colors[idx, 2]

                    if y + 1 == H or not solid[grid[y + 1, z, x]]:
                        r = min(255, int(r0 * 1.06))
                        g = min(255, int(g0 * 1.06))
                        b = min(255, int(b0 * 1.06))
                        px, py = (x - z) * (tile_w // 2) + ox, (x + z) * (tile_h // 2) - (y + 1) * block_h + oy
                        px1, py1 = ((x + 1) - z) * (tile_w // 2) + ox, ((x + 1) + z) * (tile_h // 2) - (y + 1) * block_h + oy
                        px2, py2 = ((x + 1) - (z + 1)) * (tile_w // 2) + ox, ((x + 1) + (z + 1)) * (tile_h // 2) - (y + 1) * block_h + oy
                        px3, py3 = (x - (z + 1)) * (tile_w // 2) + ox, (x + (z + 1)) * (tile_h // 2) - (y + 1) * block_h + oy
                        xs[0], ys[0], ds[0] = px, py, x + z + y + 1
                        xs[1], ys[1], ds[1] = px1, py1, x + 1 + z + y + 1
                        xs[2], ys[2], ds[2] = px2, py2, x + 1 + z + 1 + y + 1
                        xs[3], ys[3], ds[3] = px3, py3, x + z + 1 + y + 1
                        _draw_quad(img, depth, xs, ys, ds, r, g, b)

                    if z + 1 == L or not solid[grid[y, z + 1, x]]:
                        r = int(r0 * 0.72)
                        g = int(g0 * 0.72)
                        b = int(b0 * 0.72)
                        px, py = (x - (z + 1)) * (tile_w // 2) + ox, (x + (z + 1)) * (tile_h // 2) - (y + 1) * block_h + oy
                        px1, py1 = ((x + 1) - (z + 1)) * (tile_w // 2) + ox, ((x + 1) + (z + 1)) * (tile_h // 2) - (y + 1) * block_h + oy
                        px2, py2 = ((x + 1) - (z + 1)) * (tile_w // 2) + ox, ((x + 1) + (z + 1)) * (tile_h // 2) - y * block_h + oy
                        px3, py3 = (x - (z + 1)) * (tile_w // 2) + ox, (x + (z + 1)) * (tile_h // 2) - y * block_h + oy
                        xs[0], ys[0], ds[0] = px, py, x + z + 1 + y + 1
                        xs[1], ys[1], ds[1] = px1, py1, x + 1 + z + 1 + y + 1
                        xs[2], ys[2], ds[2] = px2, py2, x + 1 + z + 1 + y
                        xs[3], ys[3], ds[3] = px3, py3, x + z + 1 + y
                        _draw_quad(img, depth, xs, ys, ds, r, g, b)

                    if x + 1 == W or not solid[grid[y, z, x + 1]]:
                        r = int(r0 * 0.84)
                        g = int(g0 * 0.84)
                        b = int(b0 * 0.84)
                        px, py = ((x + 1) - z) * (tile_w // 2) + ox, ((x + 1) + z) * (tile_h // 2) - (y + 1) * block_h + oy
                        px1, py1 = ((x + 1) - (z + 1)) * (tile_w // 2) + ox, ((x + 1) + (z + 1)) * (tile_h // 2) - (y + 1) * block_h + oy
                        px2, py2 = ((x + 1) - (z + 1)) * (tile_w // 2) + ox, ((x + 1) + (z + 1)) * (tile_h // 2) - y * block_h + oy
                        px3, py3 = ((x + 1) - z) * (tile_w // 2) + ox, ((x + 1) + z) * (tile_h // 2) - y * block_h + oy
                        xs[0], ys[0], ds[0] = px, py, x + 1 + z + y + 1
                        xs[1], ys[1], ds[1] = px1, py1, x + 1 + z + 1 + y + 1
                        xs[2], ys[2], ds[2] = px2, py2, x + 1 + z + 1 + y
                        xs[3], ys[3], ds[3] = px3, py3, x + 1 + z + y
                        _draw_quad(img, depth, xs, ys, ds, r, g, b)


def _palette_arrays(inv):
    max_idx = max(inv)
    solid = np.zeros(max_idx + 1, dtype=np.bool_)
    colors = np.zeros((max_idx + 1, 3), dtype=np.uint8)
    for i, name in inv.items():
        solid[i] = not is_air(name)
        colors[i] = block_color(name)
    return solid, colors


def render_grid_visible_iso(grid, inv, tile_w=4, tile_h=2, block_h=3, margin=MARGIN):
    if njit is None:
        raise RuntimeError("visible-surface isometric rendering requires numba")
    H, L, W = grid.shape
    solid, colors = _palette_arrays(inv)
    hw = tile_w // 2
    hh = tile_h // 2
    width = (W + L) * hw + margin * 2
    height = (W + L) * hh + H * block_h + tile_h + margin * 2
    ox = margin + L * hw
    oy = margin + H * block_h
    img = np.zeros((int(height), int(width), 4), dtype=np.uint8)
    depth = np.full((int(height), int(width)), -1.0e20, dtype=np.float32)
    _raster_visible_iso(grid.astype(np.int32, copy=False), solid, colors, img, depth,
                        tile_w, tile_h, block_h, ox, oy)
    return Image.fromarray(img, "RGBA")


def render_schem_visible_iso(path, tile_w=4, tile_h=2, block_h=3, margin=MARGIN):
    _W, _H, _L, inv, grid = decode_schem_array(path)
    return render_grid_visible_iso(grid, inv, tile_w, tile_h, block_h, margin)


def render_cells_visible_iso(cells, tile_w=TILE_W, tile_h=TILE_H, block_h=BLOCK_H, margin=MARGIN):
    _W, _H, _L, inv, grid = cells_to_grid(cells)
    return render_grid_visible_iso(grid, inv, tile_w, tile_h, block_h, margin)


def font(size):
    for name in ("arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def write_contact(images, out, cols=8, cell_w=180, cell_h=180, pad=8):
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), CONTACT_SHEET_BG)
    d = ImageDraw.Draw(sheet)
    label_font = font(13)
    for i, (key, im) in enumerate(images):
        r, c = divmod(i, cols)
        x0, y0 = c * cell_w, r * cell_h
        scale = min((cell_w - pad * 2) / im.width, (cell_h - 28) / im.height, 1.0)
        thumb = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                          Image.Resampling.LANCZOS)
        sheet.alpha_composite(thumb, (x0 + (cell_w - thumb.width) // 2,
                                      y0 + cell_h - thumb.height - 6))
        d.text((x0 + 6, y0 + 5), key, fill=(235, 235, 235, 255), font=label_font)
    sheet.save(out)
    return sheet
