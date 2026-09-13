"""Export real builds from the world into .schem pieces and buildings.json."""

from __future__ import annotations

import json
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
from engine.schematic.writer import write_sponge_schem_cells
from pipeline.stages import noop, run_stage_cli

CATALOG = BUILD_CATALOG


@lru_cache(maxsize=1)
def get_world():
    return World()


def detect_builds(build_type, x_a, x_b, z_a, z_b, y0, y1, *, on_scan_progress=None):
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


def write_schem(cells, block_entities, path):
    write_sponge_schem_cells(cells, path, DATA_VERSION, block_entities=block_entities)


def remove_existing_schems():
    for filename in os.listdir(BUILDS_SCHEM):
        if filename.endswith(".schem"):
            os.remove(os.path.join(BUILDS_SCHEM, filename))


def run(*, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop
    os.makedirs(BUILDS_SCHEM, exist_ok=True)
    remove_existing_schems()

    region_data = [(r.build_type, *r.bounds.as_tuple()) for r in BUILD_TYPES]
    chunk_counts = [
        ((max(xa, xb) >> 4) - (min(xa, xb) >> 4) + 1) * ((max(za, zb) >> 4) - (min(za, zb) >> 4) + 1)
        for _, (xa, _y0, za), (xb, _y1, zb) in region_data
    ]
    total_scan_chunks = sum(chunk_counts)
    scan_offsets = [sum(chunk_counts[:i]) for i in range(len(chunk_counts))]

    progress(0, total_scan_chunks, "Scanning build regions...")
    builds = []
    for i, (build_type, start_xyz, end_xyz) in enumerate(region_data):
        xa, y0, za = start_xyz
        xb, y1, zb = end_xyz
        offset = scan_offsets[i]

        def on_scan(done, _total, _offset=offset):
            progress(_offset + done, total_scan_chunks, "Scanning build regions...")

        detected, skipped = detect_builds(build_type, xa, xb, za, zb, y0, y1, on_scan_progress=on_scan)
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
            cells, bes = extract_cuboid(get_world(), cuboids[0], force_persistent_leaves=True)
            write_schem(cells, bes, os.path.join(BUILDS_SCHEM, f"{key}.schem"))
            entry["pieces"]["whole"] = cuboids[0][3] - cuboids[0][2] + 1
        else:
            stack_rng = stack_sign(emerald)
            entry["stack"] = stack_rng if stack_rng is not None else [1, 1]
            for name, cuboid in zip(("bottom", "middle", "top"), cuboids):
                cells, bes = extract_cuboid(get_world(), cuboid, force_persistent_leaves=True)
                write_schem(cells, bes, os.path.join(BUILDS_SCHEM, f"{key}_{name}.schem"))
                entry["pieces"][name] = cuboid[3] - cuboid[2] + 1
        catalog[key] = entry
        logger(f"extracted {key}")
        progress(i + 1, total, key)

    with open(CATALOG, "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, indent=2)
    logger(f"wrote {len(catalog)} builds to {CATALOG}")
    return {
        "count": len(catalog),
        "catalog_path": CATALOG,
        "items": sorted(catalog),
    }


if __name__ == "__main__":
    run_stage_cli(run)
