"""Shared production road-grid schematic assembly."""

from __future__ import annotations

import glob
import os

import numpy as np

from config.algo import CELL
from engine.core.road_network import iter_placements, iter_tile_catalogue, rot_ports
from engine.schematic.grid import new_palette, stamp_tile
from engine.schematic.reader import read_tile
from engine.schematic.transform import rot_tile, translate_block_entities

# Fill props (e.g. 15_fill_1x1_A) share the road region and marker convention but
# are not road-network tiles: they fill empty lot cells in the city, so they are
# kept out of the road-grid tile set and loaded separately.
FILL_TOKEN = "fill"
GROUND_FILL_PREFIX = "18"
ROAD_TILE_PREFIXES = frozenset(name[:2] for _layer, _base, name in iter_tile_catalogue())


def load_tiles(roads_dir):
    tiles = {}
    for path in glob.glob(os.path.join(roads_dir, "*.schem")):
        name = os.path.basename(path)
        if name[:2] not in ROAD_TILE_PREFIXES:
            continue
        tiles[name[:2]] = read_tile(path)
    return tiles


def load_fillers(roads_dir):
    """Load the fill-prop tiles (self-contained, ground-seated cell fillers)."""
    return [
        read_tile(path)
        for path in sorted(glob.glob(os.path.join(roads_dir, "*.schem")))
        if FILL_TOKEN in os.path.basename(path) and os.path.basename(path)[:2] != GROUND_FILL_PREFIX
    ]


def load_ground_fill_tile(roads_dir):
    """Load the dedicated empty-lot ground filler authored as road asset 18."""
    for path in sorted(glob.glob(os.path.join(roads_dir, "*.schem"))):
        if os.path.basename(path)[:2] == GROUND_FILL_PREFIX:
            return read_tile(path)
    return None


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
    vector_base = {name[:2]: base for _layer, base, name in iter_tile_catalogue()}
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
        (p.tile_name[:2], p.rotation, p.fx * CELL, p.fy * CELL)
        for p in iter_placements(net, layers=("big", "small", "mixed"))
    ]


def build(net, tiles):
    """Stamp every road tile of ``net`` into one voxel grid; ``tiles`` is from :func:`load_tiles`."""
    road_ground_offsets = {tile.ground_offset for tile in tiles.values()}
    if len(road_ground_offsets) > 1:
        raise ValueError(f"road assets disagree on ground offsets: {sorted(road_ground_offsets)}")
    road_ground_offset = next(iter(road_ground_offsets), 0)
    offsets = schem_offsets(tiles)
    span = net["size"].span
    max_height = max(tile.height for tile in tiles.values())
    grid = np.zeros((max_height, span, span), dtype=np.int16)
    palette = new_palette()
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
        stamp_tile(grid, palette, tile, bx, 0, bz)
        block_entities += translate_block_entities(tile.block_entities, bx, 0, bz)
        count += 1
    return grid, palette, (span, max_height, span), count, road_ground_offset, block_entities
