"""Sponge v3 ``.schem`` files: tiles and their rotation, reading and writing, and the voxel grids tiles are stamped
into."""

from __future__ import annotations

import os
from collections import namedtuple
from dataclasses import dataclass, field

import nbtlib
import numpy as np
from nbtlib import ByteArray, Compound, Int, IntArray, List, Short, String

from citygen.tools.blocks import format_state, is_air, parse_state


# --- Tiles, and turning them

FACING_CW = {"north": "east", "east": "south", "south": "west", "west": "north"}
CONN_SRC = {"east": "north", "south": "east", "west": "south", "north": "west"}


# A block entity travelling with a tile: local (x, y, z) within the tile's cells,
# the namespaced id ("minecraft:chest"), and ``data`` -- an nbtlib Compound of the
# rest of the block-entity NBT (contents, sign text, banner patterns, ...). The
# data is carried verbatim; only the position moves under transforms, and the
# block's own orientation lives in the cell state (rotated by ``rot_state``).
BlockEntity = namedtuple("BlockEntity", ("x", "y", "z", "id", "data"))


def translate_block_entities(block_entities, dx, dy, dz):
    """Shift every block entity by (dx, dy, dz), returning a new list."""
    return [
        be._replace(x=be.x + dx, y=be.y + dy, z=be.z + dz)
        for be in block_entities
    ]


@dataclass(frozen=True, slots=True)
class Tile:
    width: int
    height: int
    length: int
    cells: list[list[list[str]]]
    ground_offset: int = 0
    block_entities: tuple = field(default_factory=tuple)


def rot_state(state: str, k: int) -> str:
    k %= 4
    base, props = parse_state(state)
    if k == 0 or not props:
        return state
    for _ in range(k):
        rotated = {}
        for key, val in props.items():
            if key == "facing":
                rotated[key] = FACING_CW.get(val, val)
            elif key == "axis":
                rotated[key] = {"x": "z", "z": "x"}.get(val, val)
            elif key == "rotation":
                # Standing signs/banners/skulls: 0-15 around the compass, +4 per
                # 90 degrees clockwise (matches FACING_CW's direction).
                rotated[key] = str((int(val) + 4) % 16) if val.isdigit() else val
            elif key not in ("north", "east", "south", "west"):
                rotated[key] = val
        if any(direction in props for direction in CONN_SRC):
            for new_direction, old_direction in CONN_SRC.items():
                if old_direction in props:
                    rotated[new_direction] = props[old_direction]
        props = rotated
    return format_state(base, props)


def rot_tile(tile: Tile, k: int) -> Tile:
    for _ in range(k % 4):
        width, length = tile.width, tile.length
        new = [[[None] * length for _ in range(width)] for _ in range(tile.height)]
        for y in range(tile.height):
            for z in range(length):
                for x in range(width):
                    new[y][x][length - 1 - z] = rot_state(tile.cells[y][z][x], 1)
        # A cell at (x, z) moves to (length - 1 - z, x); block entities follow.
        rotated_bes = tuple(
            be._replace(x=length - 1 - be.z, z=be.x) for be in tile.block_entities
        )
        tile = Tile(length, tile.height, width, new, tile.ground_offset, rotated_bes)
    return tile


# --- Reading


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


def read_tile(path):
    """A ``.schem`` as a Tile; its ground offset is recovered from the stored Y offset."""
    cells = decode_schem_cells(path)
    height, length, width = len(cells), len(cells[0]), len(cells[0][0])
    _x, y, _z = decode_schem_offset(path)
    return Tile(
        width, height, length, cells,
        ground_offset=max(0, -y),
        block_entities=tuple(decode_schem_block_entities(path)),
    )


def decode_schem_array(path):
    width, height, length, inv, vals = decode_schem(path)
    return width, height, length, inv, vals.reshape(height, length, width)


# --- Writing


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


def _block_entities_tag(block_entities):
    """Sponge v3 ``BlockEntities`` list from BlockEntity records.

    The extra NBT is nested under a ``Data`` compound alongside ``Id``/``Pos``.
    """
    entries = []
    for be in block_entities or ():
        pos = IntArray([int(be.x), int(be.y), int(be.z)])
        data = Compound(be.data) if be.data else Compound({})
        entry = Compound({"Id": String(be.id), "Pos": pos})
        if len(data):
            entry["Data"] = data
        entries.append(entry)
    return List[Compound](entries)


def _schem_file(width, height, length, palette, data, data_version, offset=None, block_entities=None):
    if offset is None:
        offset = (0, 0, 0)
    offset_tag = IntArray([int(offset[0]), int(offset[1]), int(offset[2])])
    palette_tag = Compound({key: Int(value) for key, value in palette.items()})
    blocks = Compound({
        "Palette": palette_tag,
        "Data": ByteArray(data),
        "BlockEntities": _block_entities_tag(block_entities),
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


# --- Palette-indexed voxel grids that tiles are stamped into
# A grid is a numpy array indexed ``[y][z][x]`` whose values index a
# ``{block_state: index}`` palette with air at 0.


def new_palette():
    return {"minecraft:air": 0}


def intern_state(palette, state):
    """Palette index of ``state``, adding it on first use."""
    index = palette.get(state)
    if index is None:
        index = palette[state] = len(palette)
    return index


def stamp_tile(grid, palette, tile, px, py, pz, footprint=None):
    """Write a tile's non-air cells into ``grid`` with its origin at (px, py, pz).

    Cells outside the grid are clipped. When a ``footprint`` (z, x) mask is
    given, every column that receives a block is marked in it.
    """
    max_height, span_z, span_x = grid.shape
    for y in range(tile.height):
        gy = py + y
        if not (0 <= gy < max_height):
            continue
        for z in range(tile.length):
            gz = pz + z
            if not (0 <= gz < span_z):
                continue
            row = tile.cells[y][z]
            for x in range(tile.width):
                state = row[x]
                if is_air(state):
                    continue
                gx = px + x
                if not (0 <= gx < span_x):
                    continue
                if footprint is not None:
                    footprint[gz, gx] = True
                grid[gy, gz, gx] = intern_state(palette, state)
