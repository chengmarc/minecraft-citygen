"""Prod pipeline: render exported road .schem assets as isometric PNGs."""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)  # shared modules live in the repo root
from engine.isometric_renderer import render_cells_visible_iso, write_contact
from engine.schematic_reader import decode_schem_cells
from config_path import ROADS_PROD, ROADS_PROD_SCHEM
from config_render import ROAD_ASSET_ISO_BLOCK_H, ROAD_ASSET_ISO_TILE_H, ROAD_ASSET_ISO_TILE_W

SCHEM = ROADS_PROD_SCHEM


def main():
    os.makedirs(ROADS_PROD, exist_ok=True)
    images = []
    for path in sorted(glob.glob(os.path.join(SCHEM, "*.schem"))):
        name = os.path.splitext(os.path.basename(path))[0]
        im = render_cells_visible_iso(
            decode_schem_cells(path),
            tile_w=ROAD_ASSET_ISO_TILE_W,
            tile_h=ROAD_ASSET_ISO_TILE_H,
            block_h=ROAD_ASSET_ISO_BLOCK_H,
        )
        out = os.path.join(ROADS_PROD, name + ".png")
        im.save(out)
        images.append((name, im))
        print(f"saved {out} ({im.width}x{im.height})")

    contact = os.path.join(ROADS_PROD, "_contact_sheet.png")
    write_contact(images, contact, cols=5, cell_w=220, cell_h=190)
    print(f"rendered {len(images)} roads -> {contact}")


if __name__ == "__main__":
    main()
