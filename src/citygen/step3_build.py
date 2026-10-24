"""Step 3, the Build tab's run: the city as one ``.schem`` (road grid, seated buildings, lot fill), its isometric
render, and a copy of the source world with the city written in.
"""

from __future__ import annotations

import os

from citygen.core.assemble import (
    assemble_instances, BUILD_SNAP_DROP, build_road_grid, city_ground_y, compose_grid, finalize_block_entities,
    load_fillers, load_ground_fill_tile, load_tiles, max_grid_height, place_lot_fill, PLAYER_ANCHOR_MARGIN, seat_y,
    stamp_anchor_column,
)
from citygen.core.city_layout import FILLER_STREAM, plan_city, seeded_rng
from citygen.core.road_network import gen_networks, make_size
from citygen.paths import (
    BUILD_CATALOG, BUILDS_SCHEM, city_render_path, city_schem_path, exported_world_name, exported_world_path,
    ROADS_SCHEM, WORLD_ICON,
)
from citygen.tools.render_isometric import render_schem_visible_iso, trim_to_content
from citygen.tools.schem import read_catalog, write_sponge_schem_grid
from citygen.tools.world_reader import source_data_version
from citygen.tools.world_writer import schem_to_world

# What construction reports as it starts each of its steps, in order; gui/static/progress/steps.js weights each one.
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


def run(seed, algo, save, progress):
    """Build the city of ``seed`` under ``algo``, render it, and write it into a copy of the ``save`` world.

    The city is stamped with the source world's version (see ``source_data_version``). ``progress(step, completed,
    total, detail)`` reports ``construct`` (whose detail names the step it's starting), ``render``, then ``world``.
    """
    construct(seed, algo, source_data_version(save), lambda n: progress(
        "construct", n, len(STEPS), STEPS[n] if n < len(STEPS) else None,
    ))
    schem = city_schem_path(seed)
    progress("render", 0, 1)
    image = trim_to_content(render_schem_visible_iso(schem))   # no empty sky above the tallest building
    out = city_render_path(seed)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    image.save(out)
    progress("render", 1, 1)
    schem_to_world(
        schem, exported_world_path(seed), source_world=save, world_name=exported_world_name(seed),
        icon_path=WORLD_ICON, progress=lambda completed, total, _detail: progress("world", completed, total),
    )


def construct(seed, algo, data_version, step):
    """Compose the city's voxel grid and write it as ``city_schem_path(seed)``; ``step(n)`` as step ``n`` starts."""
    size = make_size(algo.fine)

    step(0)
    network = gen_networks(seed, size, algo)

    step(1)
    road_grid, road_palette, (road_span, road_height, _), _count, road_ground_offset, road_block_entities = (
        build_road_grid(network, load_tiles(ROADS_SCHEM))
    )

    step(2)
    catalog_meta = read_catalog(BUILD_CATALOG)

    step(3)
    _lots, placements = plan_city(seed, network, catalog_meta, algo)
    ground = city_ground_y(placements, catalog_meta)
    # `ground_y` is the shared plane roads, buildings, the dedicated lot
    # ground-fill asset, and tree props resolve against.
    ground_y = ground - BUILD_SNAP_DROP
    road_y0 = seat_y(ground_y, road_ground_offset)
    out_span = road_span + PLAYER_ANCHOR_MARGIN

    step(4)
    instances, building_top = assemble_instances(seed, placements, catalog_meta, ground_y, BUILDS_SCHEM)

    step(5)
    fillers = load_fillers(ROADS_SCHEM)
    ground_fill_tile = load_ground_fill_tile(ROADS_SCHEM)
    if ground_fill_tile is None:
        raise FileNotFoundError("missing road ground-fill asset 18 among the extracted road pieces; extract again")
    max_height = max_grid_height(road_y0, road_height, building_top, ground_y, fillers, ground_fill_tile)
    grid, palette, build_mask, block_entities = compose_grid(
        road_grid, road_palette, road_span, road_height, road_y0, out_span, max_height, instances, road_block_entities
    )

    step(6)
    _filler_count, filler_block_entities = place_lot_fill(
        grid, palette, build_mask, network["road_cells"], size, ground_y, fillers, ground_fill_tile,
        seeded_rng(seed, FILLER_STREAM),
    )
    block_entities += filler_block_entities

    step(7)
    stamp_anchor_column(grid, palette, ground)
    write_sponge_schem_grid(
        grid, palette, city_schem_path(seed), data_version,
        # world_writer recovers the city's ground from this offset to seat the
        # exported world's ground; change both together.
        offset=(0, -(ground + 1), 0),
        block_entities=finalize_block_entities(block_entities, grid.shape),
    )
    step(len(STEPS))
