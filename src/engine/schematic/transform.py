"""Shared schematic tile transforms."""

from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass, field


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
    if k == 0 or "[" not in state:
        return state
    base, inner = state[:state.index("[")], state[state.index("[") + 1:-1]
    props = dict(kv.split("=") for kv in inner.split(","))
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
    return base + "[" + ",".join(f"{key}={props[key]}" for key in sorted(props)) + "]"


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
