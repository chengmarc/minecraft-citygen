"""Extract road tiles and fill props from the world into Sponge v3 .schem files."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.path import ROADS_SCHEM
from config.world import BUILD_MARKER_Y_RANGE, DATA_VERSION, ROAD_BOX
from engine.world.anvil_world_reader import World
from engine.world.marker_extract import detect_marker_assets, extract_cuboid, iter_signs
from engine.schematic.writer import write_sponge_schem_cells
from pipeline.extraction import chunk_scan_count, remove_existing_schems
from pipeline.stages import noop, run_stage_cli

(START_XYZ, END_XYZ) = ROAD_BOX.as_tuple()
X0, _Y0, Z0 = START_XYZ
X1, _Y1, Z1 = END_XYZ
OUT = ROADS_SCHEM


@lru_cache(maxsize=1)
def get_world():
    return World()


def sign_text_at(x, y, z):
    for sx, sy, sz, text in iter_signs(get_world(), x, x, z, z):
        if sx == x and sy == y and sz == z:
            return text
    return ""


def name_for(emerald):
    ex, ey, ez = emerald
    return sign_text_at(ex, ey + 1, ez).replace(" ", "").strip() or None


def run(*, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop
    os.makedirs(OUT, exist_ok=True)
    remove_existing_schems(OUT)
    total_scan_chunks = chunk_scan_count(X0, X1, Z0, Z1)
    progress(0, total_scan_chunks, "Scanning road region...")

    m_lo, m_hi = BUILD_MARKER_Y_RANGE.as_tuple()

    def on_scan(done, total):
        progress(done, total, "Scanning road region...")

    components, skipped = detect_marker_assets(
        get_world(), X0, X1, Z0, Z1, (m_lo, m_hi),
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
            os.path.join(OUT, name + ".schem"),
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
    logger(f"saved {len(results)} schematics to {OUT}")
    return {"count": len(results), "output_dir": OUT, "items": [name for name, _dims in results]}


if __name__ == "__main__":
    run_stage_cli(run)
