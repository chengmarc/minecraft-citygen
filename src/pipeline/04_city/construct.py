"""Assemble the full 3D city .schem: road grid + real builds in the lots."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.algo import CELL, DEFAULT_SEED, FINE as DEFAULT_FINE
from config.path import city_schem_path
from config.render import CITY_ANCHOR_BLOCK, CITY_GROUND_Y
from config.world import DATA_VERSION
from engine.blocks import is_air
from engine.schematic.grid import intern_state, new_palette, stamp_tile
from engine.schematic.building import assemble, is_stacked, read_catalog
from engine.core.city_layout import (
    FACE_K,
    FILLER_STREAM,
    STACK_HEIGHT_STREAM,
    placement_origin,
    plan_city,
    seeded_rng,
)
from engine.core.road_network import gen_networks, make_size
from engine.schematic.road import build as build_road_grid
from engine.schematic.road import load_fillers
from engine.schematic.road import load_ground_fill_tile
from engine.schematic.transform import rot_tile, translate_block_entities
from engine.schematic.writer import write_sponge_schem_grid
from pipeline.stages import noop, run_stage_cli

BUILD_SNAP_DROP = 1
PLAYER_ANCHOR_MARGIN = 1

# Progress steps reported by run(), in order; the GUI weights mirror this.
STEPS = (
    "Generating road network",
    "Building road grid",
    "Loading building catalog",
    "Planning placements",
    "Assembling building instances",
    "Composing voxel grid",
    "Placing trees and filling lots",
    "Writing schematic",
)


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
    """Bottom row of a seated asset relative to the city ground plane."""
    return ground_y - ground_offset


def _assemble_instances(seed, placements, catalog_meta, ground_y):
    """Rotate and position each placed building; return (instances, tallest building top)."""
    height_rng = seeded_rng(seed, STACK_HEIGHT_STREAM)
    instances = []
    building_top = 0
    for placement in placements:
        building = placement.building
        entry = catalog_meta[building.num]
        mid_sections = height_rng.randint(*entry.get("stack", [1, 1])) if is_stacked(entry) else 0
        tile = rot_tile(assemble(building.num, mid_sections, catalog_meta), FACE_K[placement.facing])
        px, pz = placement_origin(placement.rect, placement.facing, tile.width, tile.length, CELL)
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
    master_palette = new_palette()
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
        stamp_tile(grid, master_palette, tile, px, y0, pz, build_mask)
        block_entities += translate_block_entities(tile.block_entities, px, y0, pz)
    return grid, master_palette, build_mask, block_entities


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
                if not is_air(ground_fill_tile.cells[dy][pz][px])
            ]
            if column:
                pattern_columns[(px, pz)] = column
    for fy in range(size.fine):
        for fx in range(size.fine):
            if (fx, fy) in road_cells or (fx, fy) in skip_cells:
                continue
            z0 = PLAYER_ANCHOR_MARGIN + fy * CELL
            z1 = PLAYER_ANCHOR_MARGIN + (fy + 1) * CELL
            x0 = PLAYER_ANCHOR_MARGIN + fx * CELL
            x1 = PLAYER_ANCHOR_MARGIN + (fx + 1) * CELL
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
                            grid[gy, gz, gx] = intern_state(master_palette, state)
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
            z0 = PLAYER_ANCHOR_MARGIN + fy * CELL
            x0 = PLAYER_ANCHOR_MARGIN + fx * CELL
            if build_mask[z0:z0 + CELL, x0:x0 + CELL].any():
                continue
            tile = rot_tile(rng.choice(fillers), rng.randint(0, 3))
            y0 = _seat_y(ground_y, tile.ground_offset)
            stamp_tile(grid, master_palette, tile, x0, y0, z0)
            block_entities += translate_block_entities(tile.block_entities, x0, y0, z0)
            placed.add((fx, fy))
    return placed, block_entities


def _load_fill_assets(no_ground_fill):
    if no_ground_fill:
        return [], None
    fillers = load_fillers()
    ground_fill_tile = load_ground_fill_tile()
    if ground_fill_tile is None:
        raise FileNotFoundError(
            "missing road ground-fill asset 18 in artifacts/01_roads/schem; run Stage 1 first"
        )
    return fillers, ground_fill_tile


def _max_grid_height(road_y0, road_height, building_top, ground_y, fillers, ground_fill_tile):
    filler_top = max((_seat_y(ground_y, tile.ground_offset) + tile.height for tile in fillers), default=0)
    ground_fill_top = (
        _seat_y(ground_y, ground_fill_tile.ground_offset) + ground_fill_tile.height
        if ground_fill_tile is not None
        else 0
    )
    return max(road_y0 + road_height, building_top, filler_top, ground_fill_top)


def _place_lot_fill(grid, master_palette, build_mask, road_cells, size, ground_y, fillers, ground_fill_tile, seed):
    if ground_fill_tile is None:
        return 0, []

    block_entities = []
    tree_cells = set()
    if fillers:
        filler_rng = seeded_rng(seed, FILLER_STREAM)
        tree_cells, filler_block_entities = _place_fillers(
            grid, master_palette, build_mask, road_cells, size, ground_y, fillers, filler_rng
        )
        block_entities += filler_block_entities
    block_entities += _place_ground_fill(
        grid, master_palette, build_mask, road_cells, size, ground_y, ground_fill_tile, tree_cells
    )
    return len(tree_cells), block_entities


def _write_city_schematic(
    grid,
    master_palette,
    block_entities,
    out,
    city_ground_y,
    seed,
    fine,
    tile_count,
    building_count,
    filler_count,
    filler_kind_count,
    logger,
):
    anchor_idx = intern_state(master_palette, CITY_ANCHOR_BLOCK)
    for y in range(city_ground_y + 1):
        grid[y, 0, 0] = anchor_idx

    block_entities = _finalize_block_entities(block_entities, grid.shape)
    max_height, out_span, _out_span_x = grid.shape
    summary = (
        f"seed={seed}, fine={fine}: roads={tile_count} tiles, buildings={building_count}, "
        f"fillers={filler_count} ({filler_kind_count} kinds), "
        f"grid {out_span}x{max_height}x{out_span}, palette={len(master_palette)}, "
        f"block_entities={len(block_entities)}"
    )
    logger(summary)
    write_sponge_schem_grid(
        grid, master_palette, out, DATA_VERSION,
        offset=(0, -(city_ground_y + 1), 0),
        block_entities=block_entities,
    )
    return summary


def run(*, seed=DEFAULT_SEED, fine=DEFAULT_FINE, out=None, no_ground_fill=False, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop

    def _step(n):
        progress(n, len(STEPS), STEPS[n] if n < len(STEPS) else "Schematic saved")

    out = out or city_schem_path(seed)
    size = make_size(fine)

    _step(0)
    network = gen_networks(seed, size=size)

    _step(1)
    road_grid, road_palette, (road_span, road_height, _), tile_count, road_ground_offset, road_block_entities = build_road_grid(network)

    _step(2)
    catalog_meta = read_catalog()

    _step(3)
    _lots, placements = plan_city(seed, network, catalog_meta)
    city_ground_y = _city_ground_y(placements, catalog_meta)
    # `ground_y` is the shared plane roads, buildings, the dedicated lot
    # ground-fill asset, and tree props resolve against.
    ground_y = city_ground_y - BUILD_SNAP_DROP
    road_y0 = _seat_y(ground_y, road_ground_offset)
    out_span = road_span + PLAYER_ANCHOR_MARGIN

    _step(4)
    instances, building_top = _assemble_instances(seed, placements, catalog_meta, ground_y)

    _step(5)
    fillers, ground_fill_tile = _load_fill_assets(no_ground_fill)
    max_height = _max_grid_height(road_y0, road_height, building_top, ground_y, fillers, ground_fill_tile)
    road_cells = network["road_cells"]
    grid, master_palette, build_mask, block_entities = _compose_grid(
        road_grid, road_palette, road_span, road_height, road_y0, out_span, max_height, instances, road_block_entities
    )

    _step(6)
    filler_count, filler_block_entities = _place_lot_fill(
        grid, master_palette, build_mask, road_cells, size, ground_y, fillers, ground_fill_tile, seed
    )
    block_entities += filler_block_entities

    _step(7)
    summary = _write_city_schematic(
        grid,
        master_palette,
        block_entities,
        out,
        city_ground_y,
        seed,
        size.fine,
        tile_count,
        len(instances),
        filler_count,
        len(fillers),
        logger,
    )
    _step(len(STEPS))
    logger(f"saved {out}")
    return {
        "output_path": out,
        "building_count": len(instances),
        "summary": summary,
    }


if __name__ == "__main__":
    run_stage_cli(run, "seed", "fine", "out", "no_ground_fill")
