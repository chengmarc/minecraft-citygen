"""The building catalog (``buildings.json``) and its pieces' ``.schem`` files.

Extraction writes the catalog and one ``.schem`` per piece; preview and build read them back through this module. An
entry is either one ``whole`` piece (``<key>.schem``) or a stack of ``bottom``/``middle``/``top`` pieces
(``<key>_<part>.schem``) whose middle can repeat.
"""

from __future__ import annotations

import json
import os

from citygen.tools.schem import read_tile, Tile

WHOLE = "whole"
STACK_PARTS = ("bottom", "middle", "top")
DEFAULT_STACK = [1, 1]

_piece = {}  # path -> ((mtime_ns, size), Tile)


def read_catalog(catalog_path):
    with open(catalog_path, encoding="utf-8") as fh:
        return json.load(fh)


def write_catalog(catalog, catalog_path):
    with open(catalog_path, "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, indent=2)


def new_entry(build_type, size, origin, ground_offset, pieces, stack=None):
    """An entry; ``stack``, the ``[min, max]`` middle count, is kept for a stacked building only (default ``[1, 1]``)."""
    entry = {"type": build_type, "size": size, "origin": origin, "ground_offset": ground_offset, "pieces": pieces}
    if is_stacked(entry):
        entry["stack"] = list(stack or DEFAULT_STACK)
    return entry


def is_stacked(entry):
    pieces = entry.get("pieces", {})
    return all(name in pieces for name in STACK_PARTS)


def middle_count(entry, rng):
    """How many middle sections a placed copy of the building gets: drawn from its ``stack``, or 0 when whole."""
    return rng.randint(*entry.get("stack", DEFAULT_STACK)) if is_stacked(entry) else 0


def piece_path(builds_dir, key, part):
    name = key if part == WHOLE else f"{key}_{part}"
    return os.path.join(builds_dir, name + ".schem")


def piece(builds_dir, key, part=WHOLE):
    """One piece's Tile, cached by path while the file is unchanged.

    The app is one long-lived process, and every extraction rewrites the same
    ``<key>.schem`` names, so a cache keyed by path alone hands back the previous
    extraction's buildings.
    """
    path = piece_path(builds_dir, key, part)
    stat = os.stat(path)
    stamp = (stat.st_mtime_ns, stat.st_size)
    cached = _piece.get(path)
    if cached is None or cached[0] != stamp:
        cached = _piece[path] = (stamp, read_tile(path))
    return cached[1]


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
