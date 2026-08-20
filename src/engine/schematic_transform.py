"""Shared schematic tile transforms."""

from __future__ import annotations

from dataclasses import dataclass


FACING_CW = {"north": "east", "east": "south", "south": "west", "west": "north"}
CONN_SRC = {"east": "north", "south": "east", "west": "south", "north": "west"}


@dataclass(frozen=True, slots=True)
class Tile:
    width: int
    height: int
    length: int
    cells: list[list[list[str]]]
    ground_offset: int = 0


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
        tile = Tile(length, tile.height, width, new, tile.ground_offset)
    return tile
