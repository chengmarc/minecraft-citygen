"""City sim preview: compose road PNGs and pseudo building PNGs top-down.

This mirrors the production placement flow, but stays entirely in the 2D asset
pipeline: roads come from 01_roads_simulation, buildings come from
02_builds_simulation, and buildings.json contributes only footprint metadata.
"""
import argparse
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)  # shared modules live in the repo root
from engine import city_layout as C
from engine import road_network as R
from config_path import BUILDS_SIM, CITY_SIM
from config_render import CITY_GROUND_FILL_RGBA

BUILDS = BUILDS_SIM
_FONTS = {}


def font(size):
    if size not in _FONTS:
        for name in ("arialbd.ttf", "arial.ttf"):
            try:
                _FONTS[size] = ImageFont.truetype(name, size)
                break
            except Exception:
                continue
        else:
            _FONTS[size] = ImageFont.load_default()
    return _FONTS[size]


def load_build_asset(key):
    path = os.path.join(BUILDS, f"{key}.png")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"missing build asset {path}; run 02_builds_simulation/draw_builds.py first")
    return Image.open(path).convert("RGBA")


def paste_building(canvas, asset, key, facing, rect):
    t = R.rot_img(asset, C.FACE_K[facing])
    px, py = C.placement_origin(rect, facing, t.width, t.height, R.CELL)
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
    draw.rectangle([cx - tw // 2 - pad_x, cy - th // 2 - pad_y,
                    cx + tw // 2 + pad_x, cy + th // 2 + pad_y],
                   fill=(20, 22, 24, 210))
    draw.text((cx, cy), key, fill=(245, 240, 220, 255), font=label_font, anchor="mm")


def fill_lots(road_cells):
    canvas = Image.new("RGBA", (R.SPAN, R.SPAN))
    draw = ImageDraw.Draw(canvas)
    for fy in range(R.FINE):
        for fx in range(R.FINE):
            if (fx, fy) in road_cells:
                continue
            x0, y0 = fx * R.CELL, fy * R.CELL
            x1, y1 = x0 + R.CELL - 1, y0 + R.CELL - 1
            draw.rectangle([x0, y0, x1, y1], fill=CITY_GROUND_FILL_RGBA)
    return canvas


def render(net, placements, out, preview):
    canvas = fill_lots(net["road_cells"])
    canvas.alpha_composite(R.compose(net, R.load_assets()))
    cache = {}
    for b, facing, rect in placements:
        asset = cache.get(b.num)
        if asset is None:
            asset = cache[b.num] = load_build_asset(b.num)
        paste_building(canvas, asset, b.num, facing, rect)

    if preview:
        canvas = canvas.resize((preview, preview), Image.Resampling.NEAREST)
    canvas.save(out)
    print(f"saved {out} ({canvas.width}x{canvas.height})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--fine", type=int, default=R.FINE, help="fine grid edge in cells (even)")
    ap.add_argument("--preview", type=int, default=0, help="edge of preview png (0 = full res)")
    ap.add_argument("--out", default=None, help="default: ./seed_<seed>.png")
    args = ap.parse_args()
    out = args.out or os.path.join(CITY_SIM, f"seed_{args.seed}.png")

    R.FINE = args.fine - (args.fine % 2)
    R.COARSE = R.FINE // 2
    R.SPAN = R.FINE * R.CELL

    net = R.gen_networks(args.seed)
    road_cells = net["road_cells"]
    lots = C.find_lots(road_cells)
    rules = C.PlacementRules()
    catalog = C.load_catalog(rules)
    rng = random.Random(args.seed * 7 + 1)
    rule_state = rules.new_state(rng)

    placements = C.place_city(road_cells, lots, catalog, rng, rules, rule_state,
                              type2_frontage_cells=net["big_fine_cells"])
    C.validate_placements(road_cells, placements)

    by_type = {1: 0, 2: 0}
    for b, _facing, _rect in placements:
        by_type[b.type] += 1
    print(f"lots={len(lots)}  builds placed={len(placements)}  "
          f"(type 1={by_type[1]}, type 2={by_type[2]})")
    render(net, placements, out, args.preview)


if __name__ == "__main__":
    main()
