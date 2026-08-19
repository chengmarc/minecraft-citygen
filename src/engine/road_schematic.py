"""Shared production road-grid schematic assembly."""

from __future__ import annotations

import glob
import os

import numpy as np

from config.config_algo import CELL
from config.config_path import ROADS_PROD
from config.config_world import DATA_VERSION
from engine.road_network import (
    BIG_TILES,
    MIXED_TILES,
    SMALL_TILES,
    gen_networks,
    iter_placements,
    make_size,
    rot_ports,
)
from engine.schematic_reader import decode_schem_cells
from engine.schematic_transform import Tile, rot_tile
from engine.schematic_writer import sponge_schem_from_grid

ROADS_SCHEM = ROADS_PROD
BLOCKS_PER_FINE_CELL = CELL


def load_tiles():
    tiles = {}
    for path in glob.glob(os.path.join(ROADS_SCHEM, "*.schem")):
        name = os.path.basename(path)
        if not name[:2].isdigit():
            continue
        cells = decode_schem_cells(path)
        height, length, width = len(cells), len(cells[0]), len(cells[0][0])
        tiles[name[:2]] = Tile(width, height, length, cells)
    return tiles


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
    offsets = schem_offsets(tiles)
    span = size.span
    max_height = max(tile.height for tile in tiles.values())
    grid = np.zeros((max_height, span, span), dtype=np.int16)
    palette = {"minecraft:air": 0}
    rotated_cache = {}

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
        count += 1
    return grid, palette, (span, max_height, span), count


def to_schem(grid, palette, dims):
    _width, _height, _length = dims
    return sponge_schem_from_grid(grid, palette, DATA_VERSION)
