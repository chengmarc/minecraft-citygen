"""Export real builds from the world into .schem pieces and buildings.json."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.path import BUILD_CATALOG, BUILDS_SCHEM
from config.world import BUILD_MARKER_Y_RANGE, BUILD_TYPES, DATA_VERSION
from engine.world.anvil_world_reader import World
from engine.world.marker_extract import detect_marker_assets, extract_cuboid, iter_signs, parse_range
from engine.schematic.building import STACK_PARTS, WHOLE, piece_path, write_catalog
from engine.schematic.writer import write_sponge_schem_cells
from pipeline.extraction import chunk_scan_count, remove_existing_schems
from pipeline.stages import noop, run_stage_cli


@lru_cache(maxsize=1)
def get_world():
    return World()


def detect_builds(build_type, x_a, x_b, z_a, z_b, *, on_scan_progress=None):
    """Detect one- or three-layer builds from direct gold/diamond marker pairs."""
    m_lo, m_hi = BUILD_MARKER_Y_RANGE.as_tuple()
    components, skipped = detect_marker_assets(
        get_world(), x_a, x_b, z_a, z_b, (m_lo, m_hi),
        on_progress=on_scan_progress,
    )
    builds = [
        (build_type, c.origin, c.size, c.cuboids, c.ground_offset, c.emerald, c.boundary)
        for c in components
    ]
    return builds, skipped


def sign_text_at(x, y, z):
    for sx, sy, sz, text in iter_signs(get_world(), x, x, z, z):
        if sx == x and sy == y and sz == z:
            return text
    return ""


def stack_sign(emerald):
    ex, ey, ez = emerald
    stack_labels = (r"stack\s*:\s*",)
    return parse_range(sign_text_at(ex, ey + 1, ez), stack_labels)


def run(*, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop
    os.makedirs(BUILDS_SCHEM, exist_ok=True)
    remove_existing_schems(BUILDS_SCHEM)

    region_data = [(r.build_type, *r.bounds.as_tuple()) for r in BUILD_TYPES]
    chunk_counts = [
        chunk_scan_count(xa, xb, za, zb)
        for _, (xa, _y0, za), (xb, _y1, zb) in region_data
    ]
    total_scan_chunks = sum(chunk_counts)
    scan_offsets = [sum(chunk_counts[:i]) for i in range(len(chunk_counts))]

    progress(0, total_scan_chunks, "Scanning build regions...")
    builds = []
    for i, (build_type, start_xyz, end_xyz) in enumerate(region_data):
        xa, _y0, za = start_xyz
        xb, _y1, zb = end_xyz
        offset = scan_offsets[i]

        def on_scan(done, _total, _offset=offset):
            progress(_offset + done, total_scan_chunks, "Scanning build regions...")

        detected, skipped = detect_builds(build_type, xa, xb, za, zb, on_scan_progress=on_scan)
        builds.extend(detected)
        logger(f"type {build_type} region: {len(detected)} builds from marker pairs")
        for xmn, zmn, reason in skipped:
            logger(f"  !! boundary at x={xmn} z={zmn}: {reason} -- SKIPPED")

    catalog = {}
    total = len(builds)
    for i, (build_type, origin, size, cuboids, ground_offset, emerald, boundary) in enumerate(builds):
        key = f"{i + 1:03d}"
        progress(i, total, key)  # announce the build before its (slow) extraction

        entry = {"type": build_type, "size": size, "origin": origin, "ground_offset": ground_offset, "pieces": {}}
        if len(cuboids) == 1:
            parts = (WHOLE,)
        else:
            parts = STACK_PARTS
            stack_rng = stack_sign(emerald)
            entry["stack"] = stack_rng if stack_rng is not None else [1, 1]
        for part, cuboid in zip(parts, cuboids):
            cells, bes = extract_cuboid(get_world(), cuboid, force_persistent_leaves=True)
            write_sponge_schem_cells(cells, piece_path(key, part), DATA_VERSION, block_entities=bes)
            entry["pieces"][part] = cuboid[3] - cuboid[2] + 1
        catalog[key] = entry
        logger(f"extracted {key}")
        progress(i + 1, total, key)

    write_catalog(catalog)
    logger(f"wrote {len(catalog)} builds to {BUILD_CATALOG}")
    return {
        "count": len(catalog),
        "catalog_path": BUILD_CATALOG,
        "items": sorted(catalog),
    }


if __name__ == "__main__":
    run_stage_cli(run)
