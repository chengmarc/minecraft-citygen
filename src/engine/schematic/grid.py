"""Palette-indexed voxel grids that schematic tiles are stamped into.

A grid is a numpy array indexed ``[y][z][x]`` whose values index a
``{block_state: index}`` palette with air at 0.
"""

from __future__ import annotations

from engine.blocks import is_air


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
