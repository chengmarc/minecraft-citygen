"""Shared Sponge v3 schematic reading helpers.

CityGen only ever reads the v3 schematics it writes (the hard floor is 1.20, so
every output uses the Sponge v3 container), so this reader assumes the v3 layout:
fields nested under a ``Schematic`` key, blocks under ``Blocks`` with a ``Data``
array, block entities carrying their NBT in a ``Data`` compound.
"""

from __future__ import annotations

import nbtlib
import numpy as np
from nbtlib import Compound

from engine.schematic.transform import BlockEntity


def _load_schem(path):
    # v3 nests everything under a "Schematic" key.
    return nbtlib.load(path)["Schematic"]


def _varints(raw):
    raw = [b & 0xFF for b in raw]
    vals, i = [], 0
    while i < len(raw):
        val, shift = 0, 0
        while True:
            byte = raw[i]
            i += 1
            val |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                break
            shift += 7
        vals.append(val)
    return vals


def _varints_array(raw, palette_size):
    data = np.asarray(raw).astype(np.uint8)
    if palette_size < 16384:
        is_cont = np.zeros(data.size, dtype=bool)
        is_cont[1:] = (data[:-1] & 0x80) != 0
        starts = np.nonzero(~is_cont)[0]
        b0 = data[starts]
        vals = b0.astype(np.int32)
        two = (b0 & 0x80) != 0
        vals[two] = (b0[two] & 0x7F) | (data[starts[two] + 1].astype(np.int32) << 7)
        return vals
    return np.asarray(_varints(raw), dtype=np.int32)


def decode_schem(path):
    schem = _load_schem(path)
    width, height, length = int(schem["Width"]), int(schem["Height"]), int(schem["Length"])
    blocks = schem["Blocks"]
    inv = {int(value): key for key, value in blocks["Palette"].items()}
    vals = _varints_array(blocks["Data"], len(inv))
    expected = width * height * length
    if len(vals) != expected:
        raise ValueError(f"{path}: decoded {len(vals)} blocks, expected {expected}")
    return width, height, length, inv, vals


def decode_schem_offset(path):
    schem = _load_schem(path)
    if "Offset" not in schem:
        return (0, 0, 0)
    offset = schem["Offset"]
    return tuple(int(offset[i]) for i in range(3))


def decode_schem_block_entities(path):
    """Block entities in a Sponge v3 .schem as BlockEntity records (local coords).

    Entries live under ``Blocks.BlockEntities``, each carrying its NBT payload in a
    ``Data`` compound (absent when empty). Returns an empty list when the schematic
    has none.
    """
    entries = _load_schem(path)["Blocks"].get("BlockEntities")
    if not entries:
        return []
    result = []
    for entry in entries:
        pos = entry["Pos"]
        data = entry["Data"] if "Data" in entry else Compound({})
        result.append(
            BlockEntity(int(pos[0]), int(pos[1]), int(pos[2]), str(entry["Id"]), data)
        )
    return result


def decode_schem_cells(path):
    width, height, length, inv, vals = decode_schem(path)
    return [[[inv[vals[(y * length + z) * width + x]] for x in range(width)]
             for z in range(length)] for y in range(height)]


def decode_schem_array(path):
    width, height, length, inv, vals = decode_schem(path)
    return width, height, length, inv, vals.reshape(height, length, width)
