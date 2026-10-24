"""The city as one voxel grid: the road grid, seated buildings, and lot fill."""

from __future__ import annotations

import glob
import os

import numpy as np

from citygen.core.city_layout import FACE_K, placement_origin, seeded_rng, STACK_HEIGHT_STREAM
from citygen.core.road_network import iter_placements, iter_tile_catalogue, rot_ports
from citygen.settings import CELL
from citygen.tools.blocks import is_air
from citygen.tools.schem import (
    assemble, intern_state, is_stacked, new_palette, read_tile, rot_tile, stamp_tile, translate_block_entities,
)

# --- The road grid

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


def road_placements(net):
    return [
        (p.tile_name[:2], p.rotation, p.fx * CELL, p.fy * CELL)
        for p in iter_placements(net, layers=("big", "small", "mixed"))
    ]


def build_road_grid(net, tiles):
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
    for prefix, rotation, bx, bz in road_placements(net):
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


# --- Seating the buildings, and filling the lots
# Everything is positioned against one ground plane (``ground_y``): an asset's
# bottom row sits at ``ground_y - ground_offset``, where ``ground_offset`` is the
# authored emerald-marker height inside the asset. The grid is shifted by
# ``PLAYER_ANCHOR_MARGIN`` on x/z to leave room for the origin anchor column.

# One extra layer reserved below the road deck, so buildings can sit slightly
# lower than the roads without clipping below y=0 of the output schematic.
BUILD_SNAP_DROP = 1
PLAYER_ANCHOR_MARGIN = 1
CITY_GROUND_Y = 1  # ground plane, and the default ground_offset of an asset without one
CITY_ANCHOR_BLOCK = "minecraft:smooth_stone"  # solid block for the origin anchor column


def city_ground_y(placements, catalog_meta):
    """Ground plane high enough to seat the deepest below-ground building offset."""
    max_below_ground = max(
        (
            max(0, int(catalog_meta[placement.building.num].get("ground_offset", CITY_GROUND_Y)) - CITY_GROUND_Y)
            for placement in placements
        ),
        default=0,
    )
    return CITY_GROUND_Y + max_below_ground + BUILD_SNAP_DROP


def seat_y(ground_y, ground_offset):
    """Bottom row of a seated asset relative to the city ground plane."""
    return ground_y - ground_offset


def assemble_instances(seed, placements, catalog_meta, ground_y, builds_dir):
    """Rotate and position each placed building; return (instances, tallest building top)."""
    height_rng = seeded_rng(seed, STACK_HEIGHT_STREAM)
    instances = []
    building_top = 0
    for placement in placements:
        building = placement.building
        entry = catalog_meta[building.num]
        mid_sections = height_rng.randint(*entry.get("stack", [1, 1])) if is_stacked(entry) else 0
        tile = rot_tile(assemble(builds_dir, building.num, mid_sections, catalog_meta), FACE_K[placement.facing])
        px, pz = placement_origin(placement.rect, placement.facing, tile.width, tile.length)
        px += PLAYER_ANCHOR_MARGIN
        pz += PLAYER_ANCHOR_MARGIN
        y0 = seat_y(ground_y, int(entry.get("ground_offset", CITY_GROUND_Y)))
        instances.append((tile, px, pz, y0))
        building_top = max(building_top, y0 + tile.height)
    return instances, building_top


def max_grid_height(road_y0, road_height, building_top, ground_y, fillers, ground_fill_tile):
    filler_top = max((seat_y(ground_y, tile.ground_offset) + tile.height for tile in fillers), default=0)
    ground_fill_top = (
        seat_y(ground_y, ground_fill_tile.ground_offset) + ground_fill_tile.height
        if ground_fill_tile is not None
        else 0
    )
    return max(road_y0 + road_height, building_top, filler_top, ground_fill_top)


def compose_grid(road_grid, road_palette, road_span, road_height, road_y0, out_span, max_height, instances, road_block_entities):
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


def place_ground_fill(
    grid, master_palette, build_mask, road_cells, size, ground_y, ground_fill_tile, skip_cells=frozenset()
):
    """Seat the dedicated ground-fill asset into each empty non-road, non-building cell.

    Asset 18 follows the same emerald/gold/diamond marker convention as every
    other authored road-region asset, so it seats via the shared
    ``seat_y(ground_y, ground_offset)`` path.

    Its footprint is repeated across every block column inside each empty lot
    cell, and a pattern column is only stamped when all of its non-air blocks
    fit into currently-empty space. ``skip_cells`` excludes whole lot cells that
    already received a self-contained fill prop (15/16/17), preserving that
    prop's authored ground without mixing in asset 18 around it.
    """
    if ground_fill_tile is None:
        return
    y0 = seat_y(ground_y, ground_fill_tile.ground_offset)
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


def place_fillers(grid, master_palette, build_mask, road_cells, size, ground_y, fillers, rng):
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
            y0 = seat_y(ground_y, tile.ground_offset)
            stamp_tile(grid, master_palette, tile, x0, y0, z0)
            block_entities += translate_block_entities(tile.block_entities, x0, y0, z0)
            placed.add((fx, fy))
    return placed, block_entities


def place_lot_fill(grid, master_palette, build_mask, road_cells, size, ground_y, fillers, ground_fill_tile, filler_rng):
    """Fill props into empty lot cells, then ground fill around them; return (prop count, block entities)."""
    if ground_fill_tile is None:
        return 0, []

    block_entities = []
    tree_cells = set()
    if fillers:
        tree_cells, block_entities = place_fillers(
            grid, master_palette, build_mask, road_cells, size, ground_y, fillers, filler_rng
        )
    place_ground_fill(grid, master_palette, build_mask, road_cells, size, ground_y, ground_fill_tile, tree_cells)
    return len(tree_cells), block_entities


def finalize_block_entities(block_entities, grid_shape):
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


def stamp_anchor_column(grid, master_palette, city_ground_y):
    """Solid column at the grid origin up to the ground plane, so pastes line up."""
    anchor_idx = intern_state(master_palette, CITY_ANCHOR_BLOCK)
    for y in range(city_ground_y + 1):
        grid[y, 0, 0] = anchor_idx
