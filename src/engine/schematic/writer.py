"""Shared Sponge v2 schematic writing helpers."""

from __future__ import annotations

import os

import nbtlib
import numpy as np
from nbtlib import ByteArray, Compound, Int, IntArray, List, Short, String

# The Sponge Schematic v3 container first appears in WorldEdit 7.3.0, which only
# runs on Minecraft 1.20+. WorldEdit 7.2.x (shipping with 1.19.x and earlier)
# reads only v2 and rejects a v3 file outright -- even when its DataVersion is a
# valid older version. So the *container* version has to track the target, not
# just the block content: emit v2 below 1.20, v3 at or above it.
SPONGE_V3_MIN_DATA_VERSION = 3463  # Minecraft 1.20


def blockstate(name, props):
    if not props:
        return name
    return name + "[" + ",".join(f"{key}={props[key]}" for key in sorted(props)) + "]"


def encode_varint_scalar(n):
    out = []
    while True:
        byte = n & 0x7F
        n >>= 7
        out.append(byte | 0x80 if n else byte)
        if not n:
            return out


def encode_varint_array(flat):
    """Encode a numpy array of palette indexes as Sponge schematic varints."""
    assert int(flat.max(initial=0)) < 16384, "palette too big for 2-byte varint"
    out = bytearray()
    step = 10_000_000
    for i in range(0, flat.size, step):
        chunk = flat[i:i + step].astype(np.int64)
        low = chunk < 128
        b0 = np.where(low, chunk, (chunk & 0x7F) | 0x80).astype(np.uint8)
        lengths = np.where(low, 1, 2)
        offsets = np.zeros(chunk.size, dtype=np.int64)
        np.cumsum(lengths[:-1], out=offsets[1:])
        buf = np.zeros(int(offsets[-1] + lengths[-1]), dtype=np.uint8)
        buf[offsets] = b0
        high = np.nonzero(~low)[0]
        buf[offsets[high] + 1] = (chunk[high] >> 7).astype(np.uint8)
        out += buf.tobytes()
    return np.frombuffer(bytes(out), dtype=np.int8)


def _block_entities_tag(block_entities, *, v3):
    """Sponge ``BlockEntities`` list from BlockEntity records.

    v3 nests the extra NBT under a ``Data`` compound; v2 stores it inline
    alongside ``Id``/``Pos`` in the same compound.
    """
    entries = []
    for be in block_entities or ():
        pos = IntArray([int(be.x), int(be.y), int(be.z)])
        data = Compound(be.data) if be.data else Compound({})
        if v3:
            entry = Compound({"Id": String(be.id), "Pos": pos})
            if len(data):
                entry["Data"] = data
        else:
            entry = Compound(data)
            entry["Id"] = String(be.id)
            entry["Pos"] = pos
        entries.append(entry)
    return List[Compound](entries)


def _schem_file(width, height, length, palette, data, data_version, offset=None, block_entities=None):
    if offset is None:
        offset = (0, 0, 0)
    offset_tag = IntArray([int(offset[0]), int(offset[1]), int(offset[2])])
    palette_tag = Compound({key: Int(value) for key, value in palette.items()})
    if data_version < SPONGE_V3_MIN_DATA_VERSION:
        return _schem_file_v2(
            width, height, length, palette_tag, data, data_version, offset_tag, block_entities
        )
    blocks = Compound({
        "Palette": palette_tag,
        "Data": ByteArray(data),
        "BlockEntities": _block_entities_tag(block_entities, v3=True),
    })
    schem = Compound({
        "Version": Int(3),
        "DataVersion": Int(data_version),
        "Width": Short(width),
        "Height": Short(height),
        "Length": Short(length),
        "Offset": offset_tag,
        "Blocks": blocks,
        "Metadata": Compound({}),
    })
    return nbtlib.File({"Schematic": schem})


def _schem_file_v2(width, height, length, palette_tag, data, data_version, offset_tag, block_entities=None):
    """Sponge Schematic v2 container (WorldEdit 7.2.x / Minecraft 1.19 and older).

    Unlike v3, the fields live directly under a root tag named ``Schematic``
    (not nested under a ``Blocks`` compound), block data is stored as
    ``BlockData`` rather than ``Blocks.Data``, and the palette carries a
    ``PaletteMax`` count.
    """
    schem = Compound({
        "Version": Int(2),
        "DataVersion": Int(data_version),
        "Width": Short(width),
        "Height": Short(height),
        "Length": Short(length),
        "Offset": offset_tag,
        "PaletteMax": Int(len(palette_tag)),
        "Palette": palette_tag,
        "BlockData": ByteArray(data),
        "BlockEntities": _block_entities_tag(block_entities, v3=False),
        "Metadata": Compound({}),
    })
    file = nbtlib.File(schem)
    file.root_name = "Schematic"
    return file


def sponge_schem_from_cells(cells, data_version, offset=None, block_entities=None):
    height, length, width = len(cells), len(cells[0]), len(cells[0][0])
    palette, data = {}, []
    for y in range(height):
        for z in range(length):
            for x in range(width):
                state = cells[y][z][x]
                if state not in palette:
                    palette[state] = len(palette)
                data.extend(encode_varint_scalar(palette[state]))
    signed = [byte - 256 if byte > 127 else byte for byte in data]
    file = _schem_file(width, height, length, palette, signed, data_version, offset=offset, block_entities=block_entities)
    return file, palette


def sponge_schem_from_grid(grid, palette, data_version, offset=None, block_entities=None):
    height, length, width = grid.shape
    data = encode_varint_array(grid.reshape(-1))
    return _schem_file(width, height, length, palette, data, data_version, offset=offset, block_entities=block_entities)


def save_sponge_schem(file, path):
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    file.gzipped = True
    file.save(path)


def write_sponge_schem_cells(cells, path, data_version, offset=None, block_entities=None):
    file, palette = sponge_schem_from_cells(cells, data_version, offset=offset, block_entities=block_entities)
    save_sponge_schem(file, path)
    return palette


def write_sponge_schem_grid(grid, palette, path, data_version, offset=None, block_entities=None):
    file = sponge_schem_from_grid(grid, palette, data_version, offset=offset, block_entities=block_entities)
    save_sponge_schem(file, path)
