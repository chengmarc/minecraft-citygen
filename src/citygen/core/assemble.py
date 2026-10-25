"""The city as one voxel grid: the road grid (:func:`build_road_grid`), then seated buildings and lot fill
(:func:`assemble_city`)."""

from __future__ import annotations

from typing import Any, NamedTuple

import numpy as np

from citygen.core.city_layout import filler_rng, seat, stack_height_rng
from citygen.core.road_network import iter_placements, iter_tile_catalogue, rot_ports
from citygen.settings import CELL
from citygen.tools.blocks import is_air
from citygen.tools.catalog import assemble, middle_count
from citygen.tools.schem import intern_state, new_palette, rot_tile, stamp_tile, translate_block_entities

# --- The road grid


def _tile_port_dirs(tile):
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


def _schem_offsets(tiles):
    """How far each built .schem road tile is rotated from its vector base."""
    vector_base = {name[:2]: base for _layer, base, name in iter_tile_catalogue()}
    offsets = {}
    for prefix, tile in tiles.items():
        detected = _tile_port_dirs(tile)
        base = vector_base[prefix]
        offsets[prefix] = next(
            (k for k in range(4) if {direction for direction, _ in rot_ports(base, k)} == detected),
            0,
        )
    return offsets


def _road_placements(net):
    return [
        (p.tile_name[:2], p.rotation, p.fx * CELL, p.fy * CELL)
        for p in iter_placements(net, layers=("big", "small", "mixed"))
    ]


class RoadGrid(NamedTuple):
    """Every road tile of ``network`` stamped into one voxel grid, before it's seated on the city's ground."""
    network: dict[str, Any]
    grid: np.ndarray
    palette: dict[str, int]
    span: int
    height: int
    ground_offset: int
    block_entities: list


def build_road_grid(net, tiles):
    """Stamp every road tile of ``net`` into one voxel grid, from the network ``tiles`` of
    :func:`citygen.core.road_pieces.load_road_pieces`."""
    road_ground_offsets = {tile.ground_offset for tile in tiles.values()}
    if len(road_ground_offsets) > 1:
        raise ValueError(f"road assets disagree on ground offsets: {sorted(road_ground_offsets)}")
    road_ground_offset = next(iter(road_ground_offsets), 0)
    offsets = _schem_offsets(tiles)
    span = net["size"].span
    max_height = max(tile.height for tile in tiles.values())
    grid = np.zeros((max_height, span, span), dtype=np.int16)
    palette = new_palette()
    rotated_cache = {}
    block_entities = []

    for prefix, rotation, bx, bz in _road_placements(net):
        corrected_rotation = (rotation - offsets[prefix]) % 4
        tile = rotated_cache.get((prefix, corrected_rotation))
        if tile is None:
            tile = rotated_cache[(prefix, corrected_rotation)] = rot_tile(
                tiles[prefix], corrected_rotation
            )
        grid[:, bz:bz + tile.length, bx:bx + tile.width] = 0
        stamp_tile(grid, palette, tile, bx, 0, bz)
        block_entities += translate_block_entities(tile.block_entities, bx, 0, bz)
    return RoadGrid(net, grid, palette, span, max_height, road_ground_offset, block_entities)


# --- Seating the buildings, and filling the lots
# Everything is positioned against one ground plane (``ground_y``): an asset's
# bottom row sits at ``ground_y - ground_offset``, where ``ground_offset`` is the
# authored emerald-marker height inside the asset. The grid is shifted by
# ``_PLAYER_ANCHOR_MARGIN`` on x/z to leave room for the origin anchor column.

# One extra layer reserved below the road deck, so buildings can sit slightly
# lower than the roads without clipping below y=0 of the output schematic.
_BUILD_SNAP_DROP = 1
_PLAYER_ANCHOR_MARGIN = 1
_CITY_GROUND_Y = 1  # ground plane, and the default ground_offset of an asset without one
_CITY_ANCHOR_BLOCK = "minecraft:smooth_stone"  # solid block for the origin anchor column


def _city_ground_y(placements, catalog_meta):
    """Ground plane high enough to seat the deepest below-ground building offset."""
    max_below_ground = max(
        (
            max(0, int(catalog_meta[placement.building.num].get("ground_offset", _CITY_GROUND_Y)) - _CITY_GROUND_Y)
            for placement in placements
        ),
        default=0,
    )
    return _CITY_GROUND_Y + max_below_ground + _BUILD_SNAP_DROP


def assemble_city(seed, roads, placements, catalog_meta, road_pieces, builds_dir, stage):
    """The city as one voxel grid: ``roads`` (from :func:`build_road_grid`), each of ``placements`` assembled from the
    pieces in ``builds_dir``, and every empty lot cell filled from ``road_pieces``' fill props and ground fill, all
    seated on one ground plane.

    ``stage(n)`` as each of its three stages starts: the buildings, the grid, the lot fill. Returns ``(grid, palette,
    ground, block_entities)``, ``ground`` being the plane's height in the grid.
    """
    ground = _city_ground_y(placements, catalog_meta)
    # `ground_y` is the shared plane roads, buildings, the dedicated lot
    # ground-fill asset, and tree props resolve against.
    ground_y = ground - _BUILD_SNAP_DROP
    road_y0 = _seat_y(ground_y, roads.ground_offset)

    stage(0)
    instances, building_top = _assemble_instances(seed, placements, catalog_meta, ground_y, builds_dir)

    stage(1)
    fillers, ground_fill_tile = road_pieces.fill_props, road_pieces.ground_fill
    max_height = _max_grid_height(road_y0, roads.height, building_top, ground_y, fillers, ground_fill_tile)
    grid, palette, build_mask, block_entities = _compose_grid(roads, road_y0, max_height, instances)

    stage(2)
    filler_block_entities = _place_lot_fill(
        grid, palette, build_mask, roads.network["road_cells"], roads.network["size"], ground_y, fillers,
        ground_fill_tile, filler_rng(seed),
    )
    block_entities += filler_block_entities
    _stamp_anchor_column(grid, palette, ground)
    return grid, palette, ground, _finalize_block_entities(block_entities, grid.shape)


def _seat_y(ground_y, ground_offset):
    """Bottom row of a seated asset relative to the city ground plane."""
    return ground_y - ground_offset


def _assemble_instances(seed, placements, catalog_meta, ground_y, builds_dir):
    """Rotate and position each placed building; return (instances, tallest building top)."""
    height_rng = stack_height_rng(seed)
    instances = []
    building_top = 0
    for placement in placements:
        building = placement.building
        entry = catalog_meta[building.num]
        tile = assemble(builds_dir, building.num, middle_count(entry, height_rng), catalog_meta)
        quarter_turns, (px, pz) = seat(placement, tile.width, tile.length)
        tile = rot_tile(tile, quarter_turns)
        px += _PLAYER_ANCHOR_MARGIN
        pz += _PLAYER_ANCHOR_MARGIN
        y0 = _seat_y(ground_y, int(entry.get("ground_offset", _CITY_GROUND_Y)))
        instances.append((tile, px, pz, y0))
        building_top = max(building_top, y0 + tile.height)
    return instances, building_top


def _max_grid_height(road_y0, road_height, building_top, ground_y, fillers, ground_fill_tile):
    filler_top = max((_seat_y(ground_y, tile.ground_offset) + tile.height for tile in fillers), default=0)
    ground_fill_top = _seat_y(ground_y, ground_fill_tile.ground_offset) + ground_fill_tile.height
    return max(road_y0 + road_height, building_top, filler_top, ground_fill_top)


def _compose_grid(roads, road_y0, max_height, instances):
    """Blit the road grid and every building instance into one master voxel grid.

    Returns the grid, its palette, the footprint mask, and every block entity
    repositioned into master-grid coordinates (roads shifted by the road seat and
    anchor margin; each building by its placement origin).
    """
    master_palette = new_palette()
    for state in roads.palette:
        master_palette.setdefault(state, len(master_palette))
    out_span = roads.span + _PLAYER_ANCHOR_MARGIN
    grid = np.zeros((max_height, out_span, out_span), dtype=np.int16)
    inv_road_palette = {index: state for state, index in roads.palette.items()}
    remap = np.array([master_palette[inv_road_palette[i]] for i in range(len(roads.palette))], dtype=np.int16)
    grid[
        road_y0:road_y0 + roads.height,
        _PLAYER_ANCHOR_MARGIN:_PLAYER_ANCHOR_MARGIN + roads.span,
        _PLAYER_ANCHOR_MARGIN:_PLAYER_ANCHOR_MARGIN + roads.span,
    ] = remap[roads.grid]

    block_entities = translate_block_entities(
        roads.block_entities, _PLAYER_ANCHOR_MARGIN, road_y0, _PLAYER_ANCHOR_MARGIN
    )
    build_mask = np.zeros((out_span, out_span), dtype=bool)
    for tile, px, pz, y0 in instances:
        stamp_tile(grid, master_palette, tile, px, y0, pz, build_mask)
        block_entities += translate_block_entities(tile.block_entities, px, y0, pz)
    return grid, master_palette, build_mask, block_entities


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
            z0 = _PLAYER_ANCHOR_MARGIN + fy * CELL
            z1 = _PLAYER_ANCHOR_MARGIN + (fy + 1) * CELL
            x0 = _PLAYER_ANCHOR_MARGIN + fx * CELL
            x1 = _PLAYER_ANCHOR_MARGIN + (fx + 1) * CELL
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
            z0 = _PLAYER_ANCHOR_MARGIN + fy * CELL
            x0 = _PLAYER_ANCHOR_MARGIN + fx * CELL
            if build_mask[z0:z0 + CELL, x0:x0 + CELL].any():
                continue
            tile = rot_tile(rng.choice(fillers), rng.randint(0, 3))
            y0 = _seat_y(ground_y, tile.ground_offset)
            stamp_tile(grid, master_palette, tile, x0, y0, z0)
            block_entities += translate_block_entities(tile.block_entities, x0, y0, z0)
            placed.add((fx, fy))
    return placed, block_entities


def _place_lot_fill(grid, master_palette, build_mask, road_cells, size, ground_y, fillers, ground_fill_tile, filler_rng):
    """Fill props into empty lot cells, then ground fill around them; return the props' block entities."""
    block_entities = []
    tree_cells = set()
    if fillers:
        tree_cells, block_entities = _place_fillers(
            grid, master_palette, build_mask, road_cells, size, ground_y, fillers, filler_rng
        )
    _place_ground_fill(grid, master_palette, build_mask, road_cells, size, ground_y, ground_fill_tile, tree_cells)
    return block_entities


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


def _stamp_anchor_column(grid, master_palette, ground):
    """Solid column at the grid origin up to the ground plane, so pastes line up."""
    anchor_idx = intern_state(master_palette, _CITY_ANCHOR_BLOCK)
    for y in range(ground + 1):
        grid[y, 0, 0] = anchor_idx
