"""Shared Sponge schematic reading helpers."""

from __future__ import annotations

import nbtlib
import numpy as np


def _load_schem(path):
    # v3 nests everything under a "Schematic" key; v2 (written for pre-1.20
    # targets) keeps the fields at the root -- the root tag is *named*
    # Schematic but has no such child. decode_schem already handles the
    # BlockData/Blocks.Data layout split beneath this.
    root = nbtlib.load(path)
    return root["Schematic"] if "Schematic" in root else root


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
    src = schem["Blocks"] if "Blocks" in schem else schem
    inv = {int(value): key for key, value in src["Palette"].items()}
    raw = src["Data"] if "Data" in src else schem["BlockData"]
    vals = _varints_array(raw, len(inv))
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


def decode_schem_cells(path):
    width, height, length, inv, vals = decode_schem(path)
    return [[[inv[vals[(y * length + z) * width + x]] for x in range(width)]
             for z in range(length)] for y in range(height)]


def decode_schem_array(path):
    width, height, length, inv, vals = decode_schem(path)
    return width, height, length, inv, vals.reshape(height, length, width)
