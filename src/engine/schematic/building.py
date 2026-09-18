"""The building catalog (``buildings.json``) and its schematic pieces.

Stage 02 writes the catalog and one ``.schem`` per piece; every later stage
reads them back through this module. An entry is either one ``whole`` piece
(``<key>.schem``) or a stack of ``bottom``/``middle``/``top`` pieces
(``<key>_<part>.schem``) whose middle can repeat.
"""

from __future__ import annotations

import json
import os

from config.path import BUILD_CATALOG, BUILDS_SCHEM
from engine.schematic.reader import decode_schem_block_entities, decode_schem_cells
from engine.schematic.transform import Tile

WHOLE = "whole"
STACK_PARTS = ("bottom", "middle", "top")

_piece = {}


def read_catalog():
    with open(BUILD_CATALOG, encoding="utf-8") as fh:
        return json.load(fh)


def write_catalog(catalog):
    with open(BUILD_CATALOG, "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, indent=2)


def is_stacked(entry):
    pieces = entry.get("pieces", {})
    return all(name in pieces for name in STACK_PARTS)


def piece_path(key, part=WHOLE):
    name = key if part == WHOLE else f"{key}_{part}"
    return os.path.join(BUILDS_SCHEM, name + ".schem")


def load_piece(path):
    cells = decode_schem_cells(path)
    height, length, width = len(cells), len(cells[0]), len(cells[0][0])
    return width, height, length, cells, decode_schem_block_entities(path)


def piece(key, part=WHOLE):
    path = piece_path(key, part)
    if path not in _piece:
        _piece[path] = load_piece(path)
    return _piece[path]


def assemble(key, n_mid, catalog):
    """One building as a Tile, with ``n_mid`` middle sections when stacked."""
    if WHOLE in catalog[key].get("pieces", {}):
        width, height, length, cells, bes = piece(key)
        return Tile(width, height, length, cells, block_entities=tuple(bes))
    layers, block_entities, width, length, y_offset = [], [], None, None, 0
    for part in [STACK_PARTS[0]] + [STACK_PARTS[1]] * n_mid + [STACK_PARTS[2]]:
        width, height, length, cells, bes = piece(key, part)
        block_entities += [be._replace(y=be.y + y_offset) for be in bes]
        layers += cells
        y_offset += height
    return Tile(width, len(layers), length, layers, block_entities=tuple(block_entities))
