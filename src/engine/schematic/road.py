"""Shared production road-grid schematic assembly."""

from __future__ import annotations

import glob
import os

import numpy as np

from config.algo import CELL
from config.path import ROADS_PROD
from config.world import DATA_VERSION
from engine.core.road_network import (
    BIG_TILES,
    MIXED_TILES,
    SMALL_TILES,
    gen_networks,
    iter_placements,
    make_size,
    rot_ports,
)
from engine.schematic.reader import (
    decode_schem_block_entities,
    decode_schem_cells,
    decode_schem_offset,
)
from engine.schematic.transform import Tile, rot_tile, translate_block_entities
from engine.schematic.writer import sponge_schem_from_grid

ROADS_SCHEM = ROADS_PROD
BLOCKS_PER_FINE_CELL = CELL

# Fill props (e.g. 15_fill_1x1_A) share the road region and marker convention but
# are not road-network tiles: they fill empty lot cells in the city, so they are
# kept out of the road-grid tile set and loaded separately.
FILL_TOKEN = "fill"


def _tile_from_schem(path):
    cells = decode_schem_cells(path)
    height, length, width = len(cells), len(cells[0]), len(cells[0][0])
    _x, y, _z = decode_schem_offset(path)
    return Tile(
        width, height, length, cells,
        ground_offset=max(0, -y),
        block_entities=tuple(decode_schem_block_entities(path)),
    )


def load_tiles():
    tiles = {}
    for path in glob.glob(os.path.join(ROADS_SCHEM, "*.schem")):
        name = os.path.basename(path)
        if not name[:2].isdigit() or FILL_TOKEN in name:
            continue
        tiles[name[:2]] = _tile_from_schem(path)
    return tiles


def load_fillers():
    """Load the fill-prop tiles (self-contained, ground-seated cell fillers)."""
    return [
        _tile_from_schem(path)
        for path in sorted(glob.glob(os.path.join(ROADS_SCHEM, "*.schem")))
        if FILL_TOKEN in os.path.basename(path)
    ]


def tile_port_dirs(tile):
    """Directions (N=z0, S=zmax, W=x0, E=xmax) where road surface reaches the edge."""
    width, length, height = tile.width, tile.length, tile.height

    def road(x, z):
        return any("gray_concrete" in tile.cells[y][z][x] for y in range(height))

    xs = range(int(width * 0.25), int(width * 0.75) + 1)
    zs = range(int(length * 0.25), int(length * 0.75) + 1)
    dirs = set()
    if any(road(x, 0) for x in xs):
        dirs.add("N")
    if any(road(x, length - 1) for x in xs):
        dirs.add("S")
    if any(road(0, z) for z in zs):
        dirs.add("W")
    if any(road(width - 1, z) for z in zs):
        dirs.add("E")
    return dirs


def schem_offsets(tiles):
    """How far each built .schem road tile is rotated from its vector base."""
    vector_base = {
        name[:2]: base
        for catalogue in (BIG_TILES, SMALL_TILES, MIXED_TILES)
        for base, name in catalogue
    }
    offsets = {}
    for prefix, tile in tiles.items():
        detected = tile_port_dirs(tile)
        base = vector_base[prefix]
        offsets[prefix] = next(
            (k for k in range(4) if {direction for direction, _ in rot_ports(base, k)} == detected),
            0,
        )
    return offsets


def placements(net):
    return [
        (p.tile_name[:2], p.rotation, p.fx * BLOCKS_PER_FINE_CELL, p.fy * BLOCKS_PER_FINE_CELL)
        for p in iter_placements(net, layers=("big", "small", "mixed"))
    ]


def build(fine, seed):
    size = make_size(fine)
    net = gen_networks(seed, size=size)
    tiles = load_tiles()
    road_ground_offsets = {tile.ground_offset for tile in tiles.values()}
    if len(road_ground_offsets) > 1:
        raise ValueError(f"road assets disagree on ground offsets: {sorted(road_ground_offsets)}")
    road_ground_offset = next(iter(road_ground_offsets), 0)
    offsets = schem_offsets(tiles)
    span = size.span
    max_height = max(tile.height for tile in tiles.values())
    grid = np.zeros((max_height, span, span), dtype=np.int16)
    palette = {"minecraft:air": 0}
    rotated_cache = {}
    block_entities = []

    count = 0
    for prefix, rotation, bx, bz in placements(net):
        corrected_rotation = (rotation - offsets[prefix]) % 4
        tile = rotated_cache.get((prefix, corrected_rotation))
        if tile is None:
            tile = rotated_cache[(prefix, corrected_rotation)] = rot_tile(
                tiles[prefix], corrected_rotation
            )
        grid[:, bz:bz + tile.length, bx:bx + tile.width] = 0
        for y in range(tile.height):
            for z in range(tile.length):
                row = tile.cells[y][z]
                for x in range(tile.width):
                    state = row[x]
                    if state.startswith("minecraft:air"):
                        continue
                    idx = palette.get(state)
                    if idx is None:
                        idx = palette[state] = len(palette)
                    grid[y, bz + z, bx + x] = idx
        block_entities += translate_block_entities(tile.block_entities, bx, 0, bz)
        count += 1
    return grid, palette, (span, max_height, span), count, road_ground_offset, block_entities


def to_schem(grid, palette, dims, ground_offset=0, block_entities=None):
    _width, _height, _length = dims
    return sponge_schem_from_grid(
        grid, palette, DATA_VERSION, offset=(0, -ground_offset, 0), block_entities=block_entities
    )
