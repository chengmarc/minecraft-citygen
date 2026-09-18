"""Top-down road-layout images composed from the Stage 3 road tile PNGs."""

from __future__ import annotations

import os

from PIL import Image

from config.algo import CELL
from engine.core.road_network import iter_placements, iter_tile_catalogue


def load_assets(tiles_dir):
    assets = {}
    for _layer, _base, name in iter_tile_catalogue():
        with Image.open(os.path.join(tiles_dir, name + ".png")) as image:
            assets[name] = image.convert("RGBA")
    return assets


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
