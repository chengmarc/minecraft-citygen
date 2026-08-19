"""City sim preview: compose road PNGs and pseudo building PNGs top-down."""

from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.config_algo import DEFAULT_SEED, FINE as DEFAULT_FINE
from config.config_path import BUILDS_SIM, CITY_SIM
from config.config_render import CITY_GROUND_FILL_RGBA
from engine.city_layout import (
    FACE_K,
    PlacementRules,
    find_lots,
    load_catalog,
    place_city,
    placement_origin,
    validate_placements,
)
from engine.road_network import CELL, compose, gen_networks, load_assets, make_size, rot_img

BUILDS = BUILDS_SIM
_FONTS = {}


def font(size):
    if size not in _FONTS:
        for name in ("arialbd.ttf", "arial.ttf"):
            try:
                _FONTS[size] = ImageFont.truetype(name, size)
                break
            except OSError:
                continue
        else:
            _FONTS[size] = ImageFont.load_default()
    return _FONTS[size]


def load_build_asset(key):
    path = os.path.join(BUILDS, f"{key}.png")
    if not os.path.exists(path):
        raise FileNotFoundError(f"missing build asset {path}; run `python -m pipeline.02_builds_simulation` first")
    return Image.open(path).convert("RGBA")


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
    label_font = font(size)
    bbox = draw.textbbox((0, 0), key, font=label_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cx, cy = x + w // 2, y + h // 2
    pad_x, pad_y = 2, 1
    draw.rectangle(
        [cx - tw // 2 - pad_x, cy - th // 2 - pad_y, cx + tw // 2 + pad_x, cy + th // 2 + pad_y],
        fill=(20, 22, 24, 210),
    )
    draw.text((cx, cy), key, fill=(245, 240, 220, 255), font=label_font, anchor="mm")


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


def render(net, placements, out, preview):
    canvas = fill_lots(net["road_cells"], net["size"])
    canvas.alpha_composite(compose(net, load_assets()))
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


def run(*, seed=DEFAULT_SEED, fine=DEFAULT_FINE, preview=0, out=None, logger=None):
    out = out or os.path.join(CITY_SIM, f"seed_{seed}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    size = make_size(fine, even=True)
    net = gen_networks(seed, size=size)
    road_cells = net["road_cells"]
    lots = find_lots(road_cells, size.fine)
    rules = PlacementRules()
    catalog = load_catalog(rules)
    rng = random.Random(seed * 7 + 1)
    rule_state = rules.new_state(rng)

    placements = place_city(
        road_cells,
        lots,
        catalog,
        size.fine,
        rng,
        rules,
        rule_state,
        type2_frontage_cells=net["big_fine_cells"],
    )
    validate_placements(road_cells, placements, size.fine)

    by_type = {1: 0, 2: 0}
    for placement in placements:
        by_type[placement.building.type] += 1
    if logger is not None:
        logger(f"lots={len(lots)}  builds placed={len(placements)}  (type 1={by_type[1]}, type 2={by_type[2]})")
    width, height = render(net, placements, out, preview)
    if logger is not None:
        logger(f"saved {out} ({width}x{height})")
    return {"output_path": out, "image_size": (width, height), "placements": len(placements)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--fine", type=int, default=DEFAULT_FINE, help="fine grid edge in cells (even)")
    ap.add_argument("--preview", type=int, default=0, help="edge of preview png (0 = full res)")
    ap.add_argument("--out", default=None, help="default: ./seed_<seed>.png")
    args = ap.parse_args()
    run(seed=args.seed, fine=args.fine, preview=args.preview, out=args.out, logger=print)


if __name__ == "__main__":
    main()
