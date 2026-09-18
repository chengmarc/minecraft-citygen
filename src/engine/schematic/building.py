"""The building catalog (``buildings.json``) and its schematic pieces.

Stage 02 writes the catalog and one ``.schem`` per piece; every later stage
reads them back through this module. An entry is either one ``whole`` piece
(``<key>.schem``) or a stack of ``bottom``/``middle``/``top`` pieces
(``<key>_<part>.schem``) whose middle can repeat.
"""

from __future__ import annotations

import json
import os

from engine.schematic.reader import read_tile
from engine.schematic.transform import Tile

WHOLE = "whole"
STACK_PARTS = ("bottom", "middle", "top")

_piece = {}


def read_catalog(catalog_path):
    with open(catalog_path, encoding="utf-8") as fh:
        return json.load(fh)


def write_catalog(catalog, catalog_path):
    with open(catalog_path, "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, indent=2)


def is_stacked(entry):
    pieces = entry.get("pieces", {})
    return all(name in pieces for name in STACK_PARTS)


def piece_path(builds_dir, key, part=WHOLE):
    name = key if part == WHOLE else f"{key}_{part}"
    return os.path.join(builds_dir, name + ".schem")


def piece(builds_dir, key, part=WHOLE):
    """One piece's Tile, cached by path."""
    path = piece_path(builds_dir, key, part)
    if path not in _piece:
        _piece[path] = read_tile(path)
    return _piece[path]


def assemble(builds_dir, key, n_mid, catalog):
    """One building as a Tile, with ``n_mid`` middle sections when stacked."""
    if WHOLE in catalog[key].get("pieces", {}):
        whole = piece(builds_dir, key)
        return Tile(whole.width, whole.height, whole.length, whole.cells, block_entities=whole.block_entities)
    layers, block_entities, y_offset = [], [], 0
    for part in [STACK_PARTS[0]] + [STACK_PARTS[1]] * n_mid + [STACK_PARTS[2]]:
        tile = piece(builds_dir, key, part)
        block_entities += [be._replace(y=be.y + y_offset) for be in tile.block_entities]
        layers += tile.cells
        y_offset += tile.height
    return Tile(tile.width, len(layers), tile.length, layers, block_entities=tuple(block_entities))
