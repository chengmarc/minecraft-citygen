"""Prod pipeline: render composed city .schem files as isometric PNGs."""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)  # shared modules live in the repo root
from engine.isometric_renderer import render_schem_visible_iso
from config.config_path import CITY_PROD, CITY_PROD_SCHEM
from config.config_render import FULL_SCHEM_ISO_BLOCK_H, FULL_SCHEM_ISO_TILE_H, FULL_SCHEM_ISO_TILE_W

SCHEM = CITY_PROD_SCHEM


def main():
    os.makedirs(CITY_PROD, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(SCHEM, "*.schem"))):
        name = os.path.splitext(os.path.basename(path))[0]
        im = render_schem_visible_iso(
            path,
            tile_w=FULL_SCHEM_ISO_TILE_W,
            tile_h=FULL_SCHEM_ISO_TILE_H,
            block_h=FULL_SCHEM_ISO_BLOCK_H,
        )
        out = os.path.join(CITY_PROD, name + ".png")
        im.save(out)
        print(f"saved {out} ({im.width}x{im.height})")


if __name__ == "__main__":
    main()
