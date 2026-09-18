"""Extract road tiles and fill props from the world into Sponge v3 .schem files."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.path import ROADS_SCHEM
from config.world import BUILD_MARKER_Y_RANGE, DATA_VERSION, REGION_DIR, ROAD_BOX, SAVE
from engine.world.anvil_world_reader import World
from engine.world.marker_extract import detect_marker_assets, extract_cuboid, sign_text_above
from engine.schematic.writer import write_sponge_schem_cells
from pipeline.extraction import chunk_scan_count, remove_existing_schems
from pipeline.stages import noop, run_stage_cli

@lru_cache(maxsize=1)
def get_world():
    return World(REGION_DIR, SAVE)


def name_for(emerald):
    return sign_text_above(get_world(), emerald).replace(" ", "").strip() or None


def run(*, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop
    os.makedirs(ROADS_SCHEM, exist_ok=True)
    remove_existing_schems(ROADS_SCHEM)
    total_scan_chunks = chunk_scan_count(ROAD_BOX.x0, ROAD_BOX.x1, ROAD_BOX.z0, ROAD_BOX.z1)
    progress(0, total_scan_chunks, "Scanning road region...")

    m_lo, m_hi = BUILD_MARKER_Y_RANGE.as_tuple()

    def on_scan(done, total):
        progress(done, total, "Scanning road region...")

    components, skipped = detect_marker_assets(
        get_world(), ROAD_BOX.x0, ROAD_BOX.x1, ROAD_BOX.z0, ROAD_BOX.z1, (m_lo, m_hi),
        on_progress=on_scan,
    )
    logger(f"{len(components)} marker components")
    for xmn, zmn, reason in skipped:
        logger(f"  !! boundary at x={xmn} z={zmn}: {reason} -- SKIPPED")

    results = []
    total = len(components)
    for index, comp in enumerate(components, start=1):
        name = name_for(comp.emerald)
        progress(index - 1, total, name)  # announce the asset before its (slow) extraction
        if name is None:
            logger(f"  !! no sign above emerald {comp.emerald}")
            progress(index, total, None)
            continue
        if len(comp.cuboids) != 1:
            logger(f"  !! road asset {name} has {len(comp.cuboids)} layers; expected 1 -- SKIPPED")
            progress(index, total, name)
            continue
        cells, block_entities = extract_cuboid(get_world(), comp.cuboids[0], force_persistent_leaves=True)
        height, length, width = len(cells), len(cells[0]), len(cells[0][0])
        write_sponge_schem_cells(
            cells,
            os.path.join(ROADS_SCHEM, name + ".schem"),
            DATA_VERSION,
            offset=(0, -comp.ground_offset, 0),
            block_entities=block_entities,
        )
        logger(f"extracted {name}")
        results.append((name, (width, height, length)))
        progress(index, total, name)

    if not results:
        raise RuntimeError(
            "Road extraction found no assets in the configured region. "
            "Check the road bounds or the bundled default world content."
        )
    for name, dims in sorted(results):
        logger(f"  {name:32} {dims[0]:2}x{dims[1]}x{dims[2]:2} (WxHxL)")
    logger(f"saved {len(results)} schematics to {ROADS_SCHEM}")
    return {"count": len(results), "output_dir": ROADS_SCHEM, "items": [name for name, _dims in results]}


if __name__ == "__main__":
    run_stage_cli(run)
