"""Prod pipeline: render one isometric PNG per catalog build schematic."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)  # shared modules live in the repo root
from engine.isometric_renderer import render_cells_visible_iso, write_contact
from engine.schematic_reader import decode_schem_cells
from engine.city_layout import catalog_type
from config_path import BUILD_CATALOG, BUILDS_PROD, BUILDS_PROD_SCHEM

SCHEM = BUILDS_PROD_SCHEM
CATALOG = BUILD_CATALOG


def assemble(key, meta):
    if catalog_type(meta) == 1:
        return decode_schem_cells(os.path.join(SCHEM, f"{key}.schem"))
    cells = []
    for part in ("bottom", "middle", "top"):
        cells.extend(decode_schem_cells(os.path.join(SCHEM, f"{key}_{part}.schem")))
    return cells


def main():
    catalog = json.load(open(CATALOG))
    os.makedirs(BUILDS_PROD, exist_ok=True)

    images = []
    for key in sorted(catalog):
        im = render_cells_visible_iso(assemble(key, catalog[key]))
        out = os.path.join(BUILDS_PROD, f"{key}.png")
        im.save(out)
        images.append((key, im))
        print(f"saved {out} ({im.width}x{im.height})")

    contact = os.path.join(BUILDS_PROD, "_contact_sheet.png")
    write_contact(images, contact, cols=8, cell_w=180, cell_h=180)
    print(f"rendered {len(images)} builds -> {contact}")


if __name__ == "__main__":
    main()
