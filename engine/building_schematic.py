"""Shared production building schematic assembly."""

import json
import os

from config.config_path import BUILD_CATALOG, BUILDS_PROD_SCHEM
from engine import city_layout as C
from engine.schematic_reader import decode_schem_cells
from engine.schematic_transform import Tile

BUILDS = BUILDS_PROD_SCHEM
META = json.load(open(BUILD_CATALOG))

_piece = {}


def load_piece(path):
    cells = decode_schem_cells(path)
    height, length, width = len(cells), len(cells[0]), len(cells[0][0])
    return width, height, length, cells


def piece(name):
    if name not in _piece:
        _piece[name] = load_piece(os.path.join(BUILDS, name + ".schem"))
    return _piece[name]


def assemble(key, n_mid, meta=None):
    catalog = META if meta is None else meta
    if C.catalog_type(catalog[key]) == 1:
        width, height, length, cells = piece(key)
        return Tile(width, height, length, cells)
    layers, width, length = [], None, None
    for part in ["bottom"] + ["middle"] * n_mid + ["top"]:
        width, _height, length, cells = piece(f"{key}_{part}")
        layers += cells
    return Tile(width, len(layers), length, layers)
