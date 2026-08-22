"""Shared production building schematic assembly."""

from __future__ import annotations

import json
import os

from config.config_path import BUILD_CATALOG, BUILDS_PROD
from engine.city_layout import catalog_type
from engine.schematic_reader import decode_schem_block_entities, decode_schem_cells
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
    return width, height, length, cells, decode_schem_block_entities(path)


def piece(name):
    if name not in _piece:
        _piece[name] = load_piece(os.path.join(BUILDS, name + ".schem"))
    return _piece[name]


def assemble(key, n_mid, meta=None):
    catalog = load_catalog_meta() if meta is None else meta
    if catalog_type(catalog[key]) == 1:
        width, height, length, cells, bes = piece(key)
        return Tile(width, height, length, cells, block_entities=tuple(bes))
    layers, block_entities, width, length, y_offset = [], [], None, None, 0
    for part in ["bottom"] + ["middle"] * n_mid + ["top"]:
        width, height, length, cells, bes = piece(f"{key}_{part}")
        block_entities += [be._replace(y=be.y + y_offset) for be in bes]
        layers += cells
        y_offset += height
    return Tile(width, len(layers), length, layers, block_entities=tuple(block_entities))
