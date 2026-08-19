"""Shared production building schematic assembly."""

from __future__ import annotations

import json
import os

from config.config_path import BUILD_CATALOG, BUILDS_PROD
from engine.city_layout import catalog_type
from engine.schematic_reader import decode_schem_cells
from engine.schematic_transform import Tile

BUILDS = BUILDS_PROD
META = None

_piece = {}


def load_catalog_meta():
    global META
    if META is None:
        with open(BUILD_CATALOG, encoding="utf-8") as fh:
            META = json.load(fh)
    return META


def load_piece(path):
    cells = decode_schem_cells(path)
    height, length, width = len(cells), len(cells[0]), len(cells[0][0])
    return width, height, length, cells


def piece(name):
    if name not in _piece:
        _piece[name] = load_piece(os.path.join(BUILDS, name + ".schem"))
    return _piece[name]


def assemble(key, n_mid, meta=None):
    catalog = load_catalog_meta() if meta is None else meta
    if catalog_type(catalog[key]) == 1:
        width, height, length, cells = piece(key)
        return Tile(width, height, length, cells)
    layers, width, length = [], None, None
    for part in ["bottom"] + ["middle"] * n_mid + ["top"]:
        width, _height, length, cells = piece(f"{key}_{part}")
        layers += cells
    return Tile(width, len(layers), length, layers)
