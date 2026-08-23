"""Export real builds from the world into .schem pieces and buildings.json."""

from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.path import BUILD_CATALOG, BUILDS_PROD
from config.world import BUILD_MARKER_Y_RANGE, BUILD_TYPES, DATA_VERSION, REFERENCE_GROUND_Y
from engine.world.anvil_world_reader import World
from engine.world.marker_extract import detect_assets, extract_cuboid, ground_shift, iter_signs, parse_range
from engine.schematic.writer import write_sponge_schem_cells
from pipeline.stages import noop, run_stage_cli

CATALOG = BUILD_CATALOG


@lru_cache(maxsize=1)
def get_world():
    return World()


def detect_builds(build_type, x_a, x_b, z_a, z_b, y0, y1, *, on_scan_progress=None):
    """Wrap the shared marker extraction with the per-type component count."""
    expected_components = 1 if build_type == 1 else 3
    delta = ground_shift(get_world(), x_a, x_b, z_a, z_b, REFERENCE_GROUND_Y)
    m_lo, m_hi = BUILD_MARKER_Y_RANGE.as_tuple()
    components, skipped = detect_assets(
        get_world(), x_a, x_b, z_a, z_b, y0 + delta, y1 + delta, expected_components, (m_lo + delta, m_hi + delta),
        on_progress=on_scan_progress,
    )
    builds = [
        (build_type, c.origin, c.size, c.cuboids, c.ground_y, c.boundary)
        for c in components
    ]
    return builds, skipped


def catalog_signs(xmn, xmx, zmn, zmx):
    stack_rng, appearance = None, None
    stack_labels = (r"stack\s*:\s*",)
    rep_labels = (r"appearance\s*:\s*",)
    for _x, _y, _z, text in iter_signs(get_world(), xmn, xmx, zmn, zmx):
        stack = parse_range(text, stack_labels)
        rep = parse_range(text, rep_labels)
        if stack is not None:
            stack_rng = stack
        if rep is not None:
            appearance = rep
    return stack_rng, appearance


def write_schem(cells, block_entities, path):
    write_sponge_schem_cells(cells, path, DATA_VERSION, block_entities=block_entities)


def remove_existing_schems():
    for filename in os.listdir(BUILDS_PROD):
        if filename.endswith(".schem"):
            os.remove(os.path.join(BUILDS_PROD, filename))


def run(*, logger=None, progress=None):
    logger = logger or noop
    progress = progress or noop
    os.makedirs(BUILDS_PROD, exist_ok=True)
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
        logger(f"type {build_type} region: {len(detected)} builds from wool boundaries")
        for xmn, zmn, reason in skipped:
            logger(f"  !! boundary at x={xmn} z={zmn}: {reason} -- SKIPPED")

    catalog = {}
    total = len(builds)
    for i, (build_type, origin, size, cuboids, ground_y, boundary) in enumerate(builds):
        key = f"{i + 1:03d}"
        x0, x1, z0, z1 = boundary
        stack_rng, appearance = catalog_signs(x0, x1, z0, z1)

        first_y0 = cuboids[0][2]
        entry = {"type": build_type, "size": size, "origin": origin, "ground_offset": ground_y - first_y0, "pieces": {}}
        if build_type == 1:
            cells, bes = extract_cuboid(get_world(), cuboids[0], force_persistent_leaves=True)
            write_schem(cells, bes, os.path.join(BUILDS_PROD, f"{key}.schem"))
            entry["pieces"]["whole"] = cuboids[0][3] - cuboids[0][2] + 1
        else:
            entry["stack"] = stack_rng if stack_rng is not None else [1, 1]
            entry["appearance"] = appearance if appearance is not None else [1, 1]
            for name, cuboid in zip(("bottom", "middle", "top"), cuboids):
                cells, bes = extract_cuboid(get_world(), cuboid, force_persistent_leaves=True)
                write_schem(cells, bes, os.path.join(BUILDS_PROD, f"{key}_{name}.schem"))
                entry["pieces"][name] = cuboid[3] - cuboid[2] + 1
        catalog[key] = entry
        logger(f"extracted {key}")
        progress(i + 1, total, key)

    json.dump(catalog, open(CATALOG, "w"), indent=2)
    logger(f"wrote {len(catalog)} builds to {CATALOG}")
    return {
        "count": len(catalog),
        "catalog_path": CATALOG,
        "items": sorted(catalog),
    }


if __name__ == "__main__":
    run_stage_cli(run)
