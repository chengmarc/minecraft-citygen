"""Assemble the full 3D city .schem: road grid + real builds in the lots."""

from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.algo import DEFAULT_SEED, FINE as DEFAULT_FINE
from config.path import BUILD_CATALOG, CITY_PROD, GRID_PROD
from config.render import CITY_ANCHOR_BLOCK, CITY_GROUND_Y
from config.world import DATA_VERSION
from engine.schematic.building import assemble
from engine.core.city_layout import (
    FACE_K,
    PlacementRules,
    catalog_type,
    find_lots,
    load_catalog,
    place_city,
    placement_origin,
    validate_placements,
)
from engine.core.road_network import CELL, gen_networks, make_size
from engine.schematic.road import build as build_road_grid
from engine.schematic.road import load_fillers
from engine.schematic.road import load_ground_fill_tile
from engine.schematic.reader import decode_schem
from engine.schematic.transform import rot_tile, translate_block_entities
from engine.schematic.writer import write_sponge_schem_grid
from pipeline.stages import noop, run_stage_cli

BLOCKS_PER_CELL = CELL
BUILD_SNAP_DROP = 1
PLAYER_ANCHOR_MARGIN = 1


def _resolve_fine(seed, fine):
    """Pick the fine-cell grid edge, inferring it from a saved grid schematic when unset."""
    if fine is not None:
        return fine
    grid_path = os.path.join(GRID_PROD, f"seed_{seed}.schem")
    if os.path.exists(grid_path):
        return decode_schem(grid_path)[0] // BLOCKS_PER_CELL
    return DEFAULT_FINE


def _plan_placements(seed, network, size):
    """Deterministically place buildings into the non-road lots for this seed."""
    road_cells = network["road_cells"]
    lots = find_lots(road_cells, size.fine)
    rules = PlacementRules()
    catalog = load_catalog(rules)
    place_rng = random.Random(seed * 7 + 1)
    rule_state = rules.new_state(place_rng)
    placements = place_city(
        road_cells,
        lots,
        catalog,
        size.fine,
        place_rng,
        rules,
        rule_state,
        type2_frontage_cells=network["big_fine_cells"],
    )
    validate_placements(road_cells, placements, size.fine)
    return placements


def _city_ground_y(placements, catalog_meta):
    """Ground plane high enough to seat the deepest below-ground building offset."""
    max_below_ground = max(
        (
            max(0, int(catalog_meta[placement.building.num].get("ground_offset", CITY_GROUND_Y)) - CITY_GROUND_Y)
            for placement in placements
        ),
        default=0,
    )
    return CITY_GROUND_Y + max_below_ground + BUILD_SNAP_DROP


def _seat_y(ground_y, ground_offset):
    """Bottom row of a marker asset: its emerald marker seats on the ground plane.

    Every asset authored with the gold/diamond/emerald convention (roads,
    buildings, trees) seats the same way -- the emerald marks ground level, so
    the asset's bottom sits ``ground_offset`` rows below it.
    """
    return ground_y - ground_offset


def _assemble_instances(seed, placements, catalog_meta, ground_y):
    """Rotate and position each placed building; return (instances, tallest building top)."""
    height_rng = random.Random(seed * 7 + 2)
    instances = []
    building_top = 0
    for placement in placements:
        building = placement.building
        entry = catalog_meta[building.num]
        mid_sections = height_rng.randint(*entry["stack"]) if catalog_type(entry) == 2 else 0
        tile = rot_tile(assemble(building.num, mid_sections, catalog_meta), FACE_K[placement.facing])
        px, pz = placement_origin(placement.rect, placement.facing, tile.width, tile.length, BLOCKS_PER_CELL)
        px += PLAYER_ANCHOR_MARGIN
        pz += PLAYER_ANCHOR_MARGIN
        y0 = _seat_y(ground_y, int(entry.get("ground_offset", CITY_GROUND_Y)))
        instances.append((tile, px, pz, y0))
        building_top = max(building_top, y0 + tile.height)
    return instances, building_top


def _compose_grid(road_grid, road_palette, road_span, road_height, road_y0, out_span, max_height, instances, road_block_entities):
    """Blit the road grid and every building instance into one master voxel grid.

    Returns the grid, its palette, the footprint mask, and every block entity
    repositioned into master-grid coordinates (roads shifted by the road seat and
    anchor margin; each building by its placement origin).
    """
    master_palette = {"minecraft:air": 0}
    for state in road_palette:
        master_palette.setdefault(state, len(master_palette))
    grid = np.zeros((max_height, out_span, out_span), dtype=np.int16)
    inv_road_palette = {index: state for state, index in road_palette.items()}
    remap = np.array([master_palette[inv_road_palette[i]] for i in range(len(road_palette))], dtype=np.int16)
    grid[
        road_y0:road_y0 + road_height,
        PLAYER_ANCHOR_MARGIN:PLAYER_ANCHOR_MARGIN + road_span,
        PLAYER_ANCHOR_MARGIN:PLAYER_ANCHOR_MARGIN + road_span,
    ] = remap[road_grid]

    block_entities = translate_block_entities(
        road_block_entities, PLAYER_ANCHOR_MARGIN, road_y0, PLAYER_ANCHOR_MARGIN
    )
    build_mask = np.zeros((out_span, out_span), dtype=bool)
    for tile, px, pz, y0 in instances:
        _blit_tile(grid, master_palette, tile, px, pz, y0, build_mask)
        block_entities += translate_block_entities(tile.block_entities, px, y0, pz)
    return grid, master_palette, build_mask, block_entities


def _blit_tile(grid, master_palette, tile, px, pz, y0, build_mask=None):
    """Blit a tile's non-air cells into the master grid at (px, y0, pz).

    Palette states are interned into ``master_palette`` on demand; when a
    ``build_mask`` is given, every written column is marked occupied.
    """
    max_height, span_z, span_x = grid.shape
    for y in range(tile.height):
        gy = y0 + y
        if not (0 <= gy < max_height):
            continue
        for z in range(tile.length):
            gz = pz + z
            if not (0 <= gz < span_z):
                continue
            row = tile.cells[y][z]
            for x in range(tile.width):
                state = row[x]
                if state.startswith("minecraft:air"):
                    continue
                gx = px + x
                if not (0 <= gx < span_x):
                    continue
                if build_mask is not None:
                    build_mask[gz, gx] = True
                idx = master_palette.get(state)
                if idx is None:
                    idx = master_palette[state] = len(master_palette)
                grid[gy, gz, gx] = idx


def _palette_index(master_palette, state):
    idx = master_palette.get(state)
    if idx is None:
        idx = master_palette[state] = len(master_palette)
    return idx


def _finalize_block_entities(block_entities, grid_shape):
    """Drop out-of-bounds entities and collapse duplicates on a cell (last wins).

    A schematic must not carry a block entity outside its bounds or two on the
    same position. Blits already clip blocks to the grid; this applies the same
    clipping and one-per-cell rule to the entities.
    """
    max_height, span_z, span_x = grid_shape
    by_pos = {}
    for be in block_entities:
        if 0 <= be.y < max_height and 0 <= be.z < span_z and 0 <= be.x < span_x:
            by_pos[(be.x, be.y, be.z)] = be
    return list(by_pos.values())


def _place_ground_fill(
    grid, master_palette, build_mask, road_cells, size, ground_y, ground_fill_tile, skip_cells=frozenset()
):
    """Seat the dedicated ground-fill asset into each empty non-road, non-building cell.

    Asset 18 follows the same emerald/gold/diamond marker convention as every
    other authored road-region asset, so it seats via the shared
    ``_seat_y(ground_y, ground_offset)`` path.

    Its footprint is repeated across every block column inside each empty lot
    cell, and a pattern column is only stamped when all of its non-air blocks
    fit into currently-empty space. ``skip_cells`` excludes whole lot cells that
    already received a self-contained fill prop (15/16/17), preserving that
    prop's authored ground without mixing in asset 18 around it.
    """
    if ground_fill_tile is None:
        return []
    y0 = _seat_y(ground_y, ground_fill_tile.ground_offset)
    if ground_fill_tile.block_entities:
        raise ValueError("ground-fill asset 18 must not contain block entities")
    pattern_columns = {}
    for pz in range(ground_fill_tile.length):
        for px in range(ground_fill_tile.width):
            column = [
                (dy, ground_fill_tile.cells[dy][pz][px])
                for dy in range(ground_fill_tile.height)
                if not ground_fill_tile.cells[dy][pz][px].startswith("minecraft:air")
            ]
            if column:
                pattern_columns[(px, pz)] = column
    for fy in range(size.fine):
        for fx in range(size.fine):
            if (fx, fy) in road_cells or (fx, fy) in skip_cells:
                continue
            z0 = PLAYER_ANCHOR_MARGIN + fy * BLOCKS_PER_CELL
            z1 = PLAYER_ANCHOR_MARGIN + (fy + 1) * BLOCKS_PER_CELL
            x0 = PLAYER_ANCHOR_MARGIN + fx * BLOCKS_PER_CELL
            x1 = PLAYER_ANCHOR_MARGIN + (fx + 1) * BLOCKS_PER_CELL
            for gz in range(z0, z1):
                for gx in range(x0, x1):
                    if build_mask[gz, gx]:
                        continue
                    column = pattern_columns.get(
                        ((gx - x0) % ground_fill_tile.width, (gz - z0) % ground_fill_tile.length)
                    )
                    if not column:
                        continue
                    for dy, _state in column:
                        gy = y0 + dy
                        if not (0 <= gy < grid.shape[0]) or grid[gy, gz, gx] != 0:
                            break
                    else:
                        for dy, state in column:
                            gy = y0 + dy
                            idx = master_palette.get(state)
                            if idx is None:
                                idx = master_palette[state] = len(master_palette)
                            grid[gy, gz, gx] = idx
    return []


def _place_fillers(grid, master_palette, build_mask, road_cells, size, ground_y, fillers, rng):
    """Drop a random, randomly-rotated fill prop (tree) into each empty lot cell.

    Each prop is a self-contained 9x9 asset carrying its own ground, seated on the
    ground plane like any other marker asset. Cells touched by a building are
    skipped so nothing collides with a footprint. Returns the set of (fx, fy)
    cells receiving props and the block entities they contribute, in
    master-grid coordinates.
    """
    placed = set()
    block_entities = []
    for fy in range(size.fine):
        for fx in range(size.fine):
            if (fx, fy) in road_cells:
                continue
            z0 = PLAYER_ANCHOR_MARGIN + fy * BLOCKS_PER_CELL
            x0 = PLAYER_ANCHOR_MARGIN + fx * BLOCKS_PER_CELL
            if build_mask[z0:z0 + BLOCKS_PER_CELL, x0:x0 + BLOCKS_PER_CELL].any():
                continue
            tile = rot_tile(rng.choice(fillers), rng.randint(0, 3))
            y0 = _seat_y(ground_y, tile.ground_offset)
            _blit_tile(grid, master_palette, tile, x0, z0, y0)
            block_entities += translate_block_entities(tile.block_entities, x0, y0, z0)
            placed.add((fx, fy))
    return placed, block_entities


def run(*, seed=DEFAULT_SEED, fine=None, out=None, no_ground_fill=False, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop

    def _step(n, label):
        progress(n, 8, label)

    out = out or os.path.join(CITY_PROD, f"seed_{seed}.schem")
    fine = _resolve_fine(seed, fine)
    size = make_size(fine)

    _step(0, "Building road grid")
    road_grid, road_palette, (road_span, road_height, _), tile_count, road_ground_offset, road_block_entities = build_road_grid(fine, seed)

    _step(1, "Generating road network")
    network = gen_networks(seed, size=size)

    _step(2, "Loading building catalog")
    with open(BUILD_CATALOG, encoding="utf-8") as fh:
        catalog_meta = json.load(fh)

    _step(3, "Planning placements")
    placements = _plan_placements(seed, network, size)
    city_ground_y = _city_ground_y(placements, catalog_meta)
    # `ground_y` is the single plane every marker asset seats on (emerald =
    # ground level). Roads, buildings, the dedicated lot ground-fill asset, and
    # tree props all resolve to `_seat_y(ground_y, offset)`.
    ground_y = city_ground_y - BUILD_SNAP_DROP
    road_y0 = _seat_y(ground_y, road_ground_offset)
    out_span = road_span + PLAYER_ANCHOR_MARGIN

    _step(4, "Assembling building instances")
    instances, building_top = _assemble_instances(seed, placements, catalog_meta, ground_y)

    _step(5, "Composing voxel grid")
    fillers = [] if no_ground_fill else load_fillers()
    ground_fill_tile = None if no_ground_fill else load_ground_fill_tile()
    if not no_ground_fill and ground_fill_tile is None:
        raise FileNotFoundError(
            "missing road ground-fill asset 18 in artifacts/roads/production; run road extraction first"
        )
    filler_top = max((_seat_y(ground_y, tile.ground_offset) + tile.height for tile in fillers), default=0)
    ground_fill_top = (
        _seat_y(ground_y, ground_fill_tile.ground_offset) + ground_fill_tile.height
        if ground_fill_tile is not None
        else 0
    )
    max_height = max(road_y0 + road_height, building_top, filler_top, ground_fill_top)
    road_cells = network["road_cells"]
    grid, master_palette, build_mask, block_entities = _compose_grid(
        road_grid, road_palette, road_span, road_height, road_y0, out_span, max_height, instances, road_block_entities
    )

    _step(6, "Placing trees and filling lots")
    tree_cells = set()
    if not no_ground_fill:
        if fillers:
            filler_rng = random.Random(seed * 7 + 3)
            tree_cells, filler_block_entities = _place_fillers(
                grid, master_palette, build_mask, road_cells, size, ground_y, fillers, filler_rng
            )
            block_entities += filler_block_entities
        block_entities += _place_ground_fill(
            grid, master_palette, build_mask, road_cells, size, ground_y, ground_fill_tile, tree_cells
        )

    _step(7, "Writing schematic")
    filler_count = len(tree_cells)
    anchor_idx = _palette_index(master_palette, CITY_ANCHOR_BLOCK)
    for y in range(city_ground_y + 1):
        grid[y, 0, 0] = anchor_idx

    block_entities = _finalize_block_entities(block_entities, grid.shape)
    summary = (
        f"seed={seed}, fine={fine}: roads={tile_count} tiles, buildings={len(instances)}, "
        f"fillers={filler_count} ({len(fillers)} kinds), "
        f"grid {out_span}x{max_height}x{out_span}, palette={len(master_palette)}, "
        f"block_entities={len(block_entities)}"
    )
    logger(summary)
    write_sponge_schem_grid(
        grid, master_palette, out, DATA_VERSION,
        offset=(0, -(city_ground_y + 1), 0),
        block_entities=block_entities,
    )
    _step(8, "Schematic saved")
    logger(f"saved {out}")
    return {
        "output_path": out,
        "building_count": len(instances),
        "summary": summary,
    }


if __name__ == "__main__":
    run_stage_cli(run, "seed", "fine", "out", "no_ground_fill")
