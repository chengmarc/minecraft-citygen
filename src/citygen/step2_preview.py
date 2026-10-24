"""Step 2, the Preview tab's run: flat top-down stand-ins for the road pieces and buildings, laid out as the seed's road
layout and city layout.

Nothing is built in blocks, so it's fast; but the layout comes from the same ``plan_city`` as the build, so what you
preview is what gets built.
"""

from __future__ import annotations

import os
from pathlib import Path

from citygen.core.assemble import fill_prop_paths
from citygen.core.city_layout import FILLER_STREAM, plan_city, seeded_rng
from citygen.core.road_network import gen_networks, make_size
from citygen.paths import BUILD_CATALOG, city_preview_path, grid_preview_path, ROADS_SCHEM
from citygen.tools.catalog import read_catalog
from citygen.tools.render_standins import compose, draw_building_tiles, draw_road_tiles, render_city


def run(seed, algo, progress):
    """Write the road layout and the city layout of ``seed`` under ``algo``.

    ``progress(step, completed, total)`` reports each step by its code: ``road_pieces``, ``build_pieces``,
    ``road_layout``, ``city_layout``. The road layout is saved before the city layout is started.
    """
    fill_props = [Path(path).stem for path in fill_prop_paths(ROADS_SCHEM)]   # the props the build draws from
    road_tiles = draw_road_tiles(fill_props, lambda completed, total: progress("road_pieces", completed, total))
    catalog = read_catalog(BUILD_CATALOG)
    building_tiles = draw_building_tiles(catalog, lambda completed, total: progress("build_pieces", completed, total))

    progress("road_layout", 0, 1)
    net = gen_networks(seed, make_size(algo.fine), algo)
    roads = compose(net, road_tiles)
    save(roads, grid_preview_path(seed))
    progress("road_layout", 1, 1)

    progress("city_layout", 0, 2)
    _lots, placements = plan_city(seed, net, catalog, algo)
    progress("city_layout", 1, 2)
    fillers = [road_tiles[name] for name in fill_props]
    city = render_city(net, roads, placements, building_tiles, fillers, seeded_rng(seed, FILLER_STREAM))
    save(city, city_preview_path(seed))
    progress("city_layout", 2, 2)


def save(image, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    image.save(path)
