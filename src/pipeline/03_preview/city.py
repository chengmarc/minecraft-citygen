"""City sim preview: compose road PNGs and pseudo building PNGs top-down."""

from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.algo import ALGO, CELL, DEFAULT_SEED
from config.path import BUILD_CATALOG, PREVIEW_BUILDS, PREVIEW_ROADS, city_preview_path
from config.render import CITY_GROUND_FILL_RGBA
from engine.core.city_layout import FACE_K, FILLER_STREAM, placement_origin, plan_city, seeded_rng
from engine.core.road_network import gen_networks, make_size
from engine.render.fonts import label_font
from engine.render.road_layout import compose, load_assets, rot_img
from engine.schematic.building import read_catalog
from engine.schematic.road import FILL_TOKEN
from pipeline.step import noop, run_stage_cli

def load_build_asset(key):
    path = os.path.join(PREVIEW_BUILDS, f"{key}.png")
    if not os.path.exists(path):
        raise FileNotFoundError(f"missing build asset {path}; run `python -m pipeline.stages preview` first")
    with Image.open(path) as image:
        return image.convert("RGBA")


def paste_building(canvas, asset, key, facing, rect):
    t = rot_img(asset, FACE_K[facing])
    px, py = placement_origin(rect, facing, t.width, t.height, CELL)
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


def load_fill_assets():
    """Top-down fill-prop tiles produced by Stage 3's road preview helper."""
    paths = sorted(glob.glob(os.path.join(PREVIEW_ROADS, f"*{FILL_TOKEN}*.png")))
    assets = []
    for path in paths:
        with Image.open(path) as image:
            assets.append(image.convert("RGBA"))
    return assets


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


def render(net, placements, out, preview, fillers=None, rng=None):
    canvas = fill_lots(net["road_cells"], net["size"])
    if fillers:
        occupied = {cell for placement in placements for cell in placement.rect.cells()}
        place_fill_props(canvas, net["road_cells"], occupied, net["size"], fillers, rng)
    canvas.alpha_composite(compose(net, load_assets(PREVIEW_ROADS)))
    cache = {}
    for placement in placements:
        b = placement.building
        asset = cache.get(b.num)
        if asset is None:
            asset = cache[b.num] = load_build_asset(b.num)
        paste_building(canvas, asset, b.num, placement.facing, placement.rect)

    if preview:
        canvas = canvas.resize((preview, preview), Image.Resampling.NEAREST)
    canvas.save(out)
    return canvas.width, canvas.height


def run(*, seed=DEFAULT_SEED, fine=None, algo=ALGO, preview=0, out=None, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop
    progress(0, 2, "Planning city layout")
    out = out or city_preview_path(seed)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    net = gen_networks(seed, make_size(fine or algo.fine), algo)
    lots, placements = plan_city(seed, net, read_catalog(BUILD_CATALOG), algo)

    by_type = {1: 0, 2: 0}
    for placement in placements:
        by_type[placement.building.type] += 1
    logger(f"lots={len(lots)}  builds placed={len(placements)}  (type 1={by_type[1]}, type 2={by_type[2]})")
    progress(1, 2, "Rendering city layout preview")
    fillers = load_fill_assets()
    filler_rng = seeded_rng(seed, FILLER_STREAM)
    width, height = render(net, placements, out, preview, fillers, filler_rng)
    logger(f"saved {out} ({width}x{height})")
    progress(2, 2, "Rendered city layout preview")
    return {"output_path": out, "image_size": (width, height), "placements": len(placements)}


if __name__ == "__main__":
    run_stage_cli(run, "seed", "fine", "preview", "out")
