"""Step 3, the Build tab's run: the city as one ``.schem`` (road grid, seated buildings, lot fill), its isometric
render, and a copy of the source world with the city written in.
"""

from __future__ import annotations

import os

from citygen.core.assemble import assemble_city, build_road_grid
from citygen.core.city_layout import plan_city
from citygen.core.road_network import gen_networks, make_size
from citygen.core.road_pieces import load_road_pieces
from citygen.paths import (
    BUILD_CATALOG, BUILDS_SCHEM, city_render_path, city_schem_path, exported_world_name, exported_world_path,
    ROADS_SCHEM, WORLD_ICON,
)
from citygen.tools.render_isometric import render_schem_visible_iso, trim_to_content
from citygen.tools.catalog import read_catalog
from citygen.tools.schem import write_sponge_schem_grid
from citygen.tools.world_reader import source_data_version
from citygen.tools.world_writer import schem_to_world

# How many steps construction reports, by index as it starts each (see construct); gui/static/progress/steps.js weights
# each one, and text.js words each one.
CONSTRUCT_STEPS = 8


def run(seed, algo, save, progress):
    """Build the city of ``seed`` under ``algo``, render it, and write it into a copy of the ``save`` world.

    The city is stamped with the source world's version (see ``source_data_version``). ``progress(step, completed,
    total)`` reports ``construct`` (whose ``completed`` is the index of the step it's starting), ``render``, then
    ``world``.
    """
    construct(seed, algo, source_data_version(save), lambda n: progress("construct", n, CONSTRUCT_STEPS))
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
    """Compose the city's voxel grid and write it as ``city_schem_path(seed)``; ``step(n)`` as step ``n`` starts.

    The steps: the road network, the road grid, the building catalog, the placements, then (in ``assemble_city``) the
    buildings, the voxel grid and the lot fill, and last the schematic.
    """
    step(0)
    network = gen_networks(seed, make_size(algo.fine), algo)

    step(1)
    road_pieces = load_road_pieces(ROADS_SCHEM)
    roads = build_road_grid(network, road_pieces.tiles)

    step(2)
    catalog_meta = read_catalog(BUILD_CATALOG)

    step(3)
    _lots, placements = plan_city(seed, network, catalog_meta, algo)

    grid, palette, ground, block_entities = assemble_city(
        seed, roads, placements, catalog_meta, road_pieces, BUILDS_SCHEM, lambda n: step(4 + n),
    )

    step(7)
    write_sponge_schem_grid(
        grid, palette, city_schem_path(seed), data_version,
        # world_writer recovers the city's ground from this offset to seat the
        # exported world's ground; change both together.
        offset=(0, -(ground + 1), 0),
        block_entities=block_entities,
    )
    step(CONSTRUCT_STEPS)
