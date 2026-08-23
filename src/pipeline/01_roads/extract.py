"""Extract road tiles and fill props from the world into Sponge v3 .schem files.

Road, fill, and building assets are all authored with the same marker
convention, so this stage runs the shared marker extraction (wool boundary +
gold/diamond/emerald cuboid) and simply names each result from its sign -- no
bespoke surface/marker-strip detection is needed anymore.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.path import ROADS_PROD
from config.world import BUILD_MARKER_Y_RANGE, DATA_VERSION, REFERENCE_GROUND_Y, ROAD_BOX
from engine.world.anvil_world_reader import World
from engine.world.marker_extract import detect_assets, extract_cuboid, ground_shift, iter_signs
from engine.schematic.writer import write_sponge_schem_cells
from pipeline.stages import noop, run_stage_cli

(START_XYZ, END_XYZ) = ROAD_BOX.as_tuple()
X0, Y0, Z0 = START_XYZ
X1, Y1, Z1 = END_XYZ
OUT = ROADS_PROD


@lru_cache(maxsize=1)
def get_world():
    return World()


def read_names():
    """Map each sign's (x, z) to its normalized asset name (e.g. 01_big_2x2_I)."""
    names = []
    for x, y, z, text in iter_signs(get_world(), X0, X1, Z0, Z1):
        name = text.replace(" ", "").strip()
        if name:
            names.append((x, z, name))
    return names


def name_for(boundary, names):
    xmn, xmx, zmn, zmx = boundary
    for x, z, name in names:
        if xmn <= x <= xmx and zmn <= z <= zmx:
            return name
    return None


def remove_existing_schems():
    for filename in os.listdir(OUT):
        if filename.endswith(".schem"):
            os.remove(os.path.join(OUT, filename))


def run(*, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop
    os.makedirs(OUT, exist_ok=True)
    remove_existing_schems()
    total_scan_chunks = (
        ((max(X0, X1) >> 4) - (min(X0, X1) >> 4) + 1) *
        ((max(Z0, Z1) >> 4) - (min(Z0, Z1) >> 4) + 1)
    )
    progress(0, total_scan_chunks, "Scanning road region...")

    names = read_names()
    delta = ground_shift(get_world(), X0, X1, Z0, Z1, REFERENCE_GROUND_Y)
    m_lo, m_hi = BUILD_MARKER_Y_RANGE.as_tuple()

    def on_scan(done, total):
        progress(done, total, "Scanning road region...")

    components, skipped = detect_assets(
        get_world(), X0, X1, Z0, Z1, Y0 + delta, Y1 + delta, 1, (m_lo + delta, m_hi + delta),
        on_progress=on_scan,
    )
    logger(f"source ground shift {delta:+d}; {len(names)} signs, {len(components)} marker components")
    for xmn, zmn, reason in skipped:
        logger(f"  !! boundary at x={xmn} z={zmn}: {reason} -- SKIPPED")

    results = []
    total = len(components)
    for index, comp in enumerate(components, start=1):
        name = name_for(comp.boundary, names)
        progress(index - 1, total, name)  # announce the asset before its (slow) extraction
        if name is None:
            logger(f"  !! no sign for boundary {comp.boundary}")
            progress(index, total, None)
            continue
        cells, block_entities = extract_cuboid(get_world(), comp.cuboids[0], force_persistent_leaves=True)
        height, length, width = len(cells), len(cells[0]), len(cells[0][0])
        ground_offset = comp.ground_y - comp.cuboids[0][2]
        write_sponge_schem_cells(
            cells,
            os.path.join(OUT, name + ".schem"),
            DATA_VERSION,
            offset=(0, -ground_offset, 0),
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
