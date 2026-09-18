"""Assemble the full 3D city .schem: road grid + real builds in the lots."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.algo import ALGO, DEFAULT_SEED
from config.path import BUILD_CATALOG, BUILDS_SCHEM, ROADS_SCHEM, city_schem_path
from config.world import DATA_VERSION
from engine.core.city_layout import FILLER_STREAM, plan_city, seeded_rng
from engine.core.road_network import gen_networks, make_size
from engine.schematic import city
from engine.schematic.building import read_catalog
from engine.schematic.road import build as build_road_grid
from engine.schematic.road import load_fillers, load_ground_fill_tile, load_tiles
from engine.schematic.writer import write_sponge_schem_grid
from pipeline.step import noop, run_stage_cli

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


def _load_fill_assets(no_ground_fill):
    if no_ground_fill:
        return [], None
    fillers = load_fillers(ROADS_SCHEM)
    ground_fill_tile = load_ground_fill_tile(ROADS_SCHEM)
    if ground_fill_tile is None:
        raise FileNotFoundError(
            "missing road ground-fill asset 18 in artifacts/01_roads/schem; run Stage 1 first"
        )
    return fillers, ground_fill_tile


def run(
    *, seed=DEFAULT_SEED, fine=None, algo=ALGO, data_version=DATA_VERSION, out=None, no_ground_fill=False,
    logger=None, progress=None,
):
    logger = logger or noop
    progress = progress or noop

    def _step(n):
        progress(n, len(STEPS), STEPS[n] if n < len(STEPS) else "Schematic saved")

    out = out or city_schem_path(seed)
    size = make_size(fine or algo.fine)

    _step(0)
    network = gen_networks(seed, size, algo)

    _step(1)
    road_grid, road_palette, (road_span, road_height, _), tile_count, road_ground_offset, road_block_entities = build_road_grid(network, load_tiles(ROADS_SCHEM))

    _step(2)
    catalog_meta = read_catalog(BUILD_CATALOG)

    _step(3)
    _lots, placements = plan_city(seed, network, catalog_meta, algo)
    city_ground_y = city.city_ground_y(placements, catalog_meta)
    # `ground_y` is the shared plane roads, buildings, the dedicated lot
    # ground-fill asset, and tree props resolve against.
    ground_y = city_ground_y - city.BUILD_SNAP_DROP
    road_y0 = city.seat_y(ground_y, road_ground_offset)
    out_span = road_span + city.PLAYER_ANCHOR_MARGIN

    _step(4)
    instances, building_top = city.assemble_instances(seed, placements, catalog_meta, ground_y, BUILDS_SCHEM)

    _step(5)
    fillers, ground_fill_tile = _load_fill_assets(no_ground_fill)
    max_height = city.max_grid_height(road_y0, road_height, building_top, ground_y, fillers, ground_fill_tile)
    grid, palette, build_mask, block_entities = city.compose_grid(
        road_grid, road_palette, road_span, road_height, road_y0, out_span, max_height, instances, road_block_entities
    )

    _step(6)
    filler_count, filler_block_entities = city.place_lot_fill(
        grid, palette, build_mask, network["road_cells"], size, ground_y, fillers, ground_fill_tile,
        seeded_rng(seed, FILLER_STREAM),
    )
    block_entities += filler_block_entities

    _step(7)
    city.stamp_anchor_column(grid, palette, city_ground_y)
    block_entities = city.finalize_block_entities(block_entities, grid.shape)
    summary = (
        f"seed={seed}, fine={size.fine}: roads={tile_count} tiles, buildings={len(instances)}, "
        f"fillers={filler_count} ({len(fillers)} kinds), "
        f"grid {out_span}x{max_height}x{out_span}, palette={len(palette)}, "
        f"block_entities={len(block_entities)}"
    )
    logger(summary)
    write_sponge_schem_grid(
        grid, palette, out, data_version,
        # engine.world.writer recovers city_ground_y from this offset to seat the
        # exported world's ground; change both together.
        offset=(0, -(city_ground_y + 1), 0),
        block_entities=block_entities,
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
