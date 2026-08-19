"""Export real builds from the world into .schem pieces and buildings.json."""

from __future__ import annotations

import json
import os
import re
import sys
from collections import deque
from functools import lru_cache
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.config_path import BUILD_CATALOG, BUILDS_PROD_SCHEM
from config.config_world import BUILD_MARKER_Y_RANGE, BUILD_TYPES, DATA_VERSION
from engine.anvil_world_reader import World
from engine.schematic_writer import blockstate, write_sponge_schem_cells

CATALOG = BUILD_CATALOG
MARKER_BLOCKS = {"gold_block", "diamond_block", "emerald_block"}


@lru_cache(maxsize=1)
def get_world():
    return World()


def block_base(x, y, z):
    w = get_world()
    return w.block(x, y, z)[0].split(":")[1]


def wool_boundary_components(x_a, x_b, z_a, z_b, y0, y1):
    xlo, xhi = min(x_a, x_b), max(x_a, x_b)
    zlo, zhi = min(z_a, z_b), max(z_a, z_b)
    occ = set()
    for x in range(xlo, xhi + 1):
        for z in range(zlo, zhi + 1):
            if any(block_base(x, y, z).endswith("wool") for y in range(y0, y1 + 1)):
                occ.add((x, z))

    seen, components = set(), []
    for start in occ:
        if start in seen:
            continue
        q, cells = deque([start]), []
        seen.add(start)
        while q:
            x, z = q.popleft()
            cells.append((x, z))
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                pos = (x + dx, z + dz)
                if pos in occ and pos not in seen:
                    seen.add(pos)
                    q.append(pos)
        xs = [x for x, _z in cells]
        zs = [z for _x, z in cells]
        components.append((min(xs), max(xs), min(zs), max(zs)))
    return sorted(components, key=lambda bb: (bb[2], bb[0]))


def markers_in_bounds(xmn, xmx, zmn, zmx):
    found = {kind: [] for kind in MARKER_BLOCKS}
    ylo, yhi = BUILD_MARKER_Y_RANGE.as_tuple()
    for x in range(xmn, xmx + 1):
        for z in range(zmn, zmx + 1):
            for y in range(ylo, yhi + 1):
                base = block_base(x, y, z)
                if base in MARKER_BLOCKS:
                    found[base].append((x, y, z))
    for values in found.values():
        values.sort(key=lambda pos: (pos[1], pos[2], pos[0]))
    return found


def component_cuboids(golds, diamonds):
    if len(golds) != len(diamonds) or not golds:
        raise ValueError(f"expected matching gold/diamond markers, got G={golds} D={diamonds}")

    cuboids = []
    for gold, diamond in zip(sorted(golds, key=lambda pos: pos[1]), sorted(diamonds, key=lambda pos: pos[1])):
        x0, x1 = sorted((gold[0], diamond[0]))
        y0, y1 = sorted((gold[1], diamond[1]))
        z0, z1 = sorted((gold[2], diamond[2]))
        cuboids.append((x0, x1, y0, y1, z0, z1))
    return sorted(cuboids, key=lambda bb: (bb[2], bb[4], bb[0]))


def detect_builds(build_type, x_a, x_b, z_a, z_b, y0, y1):
    expected_components = 1 if build_type == 1 else 3
    builds, skipped = [], []

    for xmn, xmx, zmn, zmx in wool_boundary_components(x_a, x_b, z_a, z_b, y0, y1):
        markers = markers_in_bounds(xmn, xmx, zmn, zmx)
        emeralds = markers["emerald_block"]
        try:
            if len(emeralds) != 1:
                raise ValueError(f"expected one emerald marker, got {emeralds}")
            cuboids = component_cuboids(markers["gold_block"], markers["diamond_block"])
            if len(cuboids) != expected_components:
                raise ValueError(f"expected {expected_components} component(s), got {len(cuboids)}")
        except ValueError as exc:
            skipped.append((xmn, zmn, str(exc)))
            continue

        footprint_x0 = min(bb[0] for bb in cuboids)
        footprint_x1 = max(bb[1] for bb in cuboids)
        footprint_z0 = min(bb[4] for bb in cuboids)
        footprint_z1 = max(bb[5] for bb in cuboids)
        width = footprint_x1 - footprint_x0 + 1
        depth = footprint_z1 - footprint_z0 + 1
        builds.append((build_type, [footprint_x0, footprint_z0, y0], [width, depth], cuboids, emeralds[0][1], (xmn, xmx, zmn, zmx)))

    return builds, skipped


def sign_text(be):
    parts = []
    for side in ("front_text", "back_text"):
        for message in be.get(side, {}).get("messages", []):
            text = str(message)
            try:
                parsed = json.loads(text)
                text = parsed.get("text", text) if isinstance(parsed, dict) else text
            except Exception:
                pass
            if text:
                parts.append(text)
    return " ".join(parts)


def parse_range(text, labels):
    for label in labels:
        pattern = rf"{label}\s*(\d+)(?:\s*-\s*(\d+))?"
        match = re.search(pattern, text, re.I)
        if match:
            lo = int(match.group(1))
            hi = int(match.group(2)) if match.group(2) else lo
            return [min(lo, hi), max(lo, hi)]
    return None


def catalog_signs(xmn, xmx, zmn, zmx):
    w = get_world()
    stack_rng, appearance, strip = None, None, []
    stack_labels = (r"stack\s*:\s*",)
    rep_labels = (r"appearance\s*:\s*",)
    for cx in range(xmn >> 4, (xmx >> 4) + 1):
        for cz in range(zmn >> 4, (zmx >> 4) + 1):
            chunk = w._load_chunk(cx, cz)
            if chunk is None:
                continue
            for be in chunk.get("block_entities", []):
                if "sign" not in str(be.get("id", "")):
                    continue
                x, y, z = int(be["x"]), int(be["y"]), int(be["z"])
                if not (xmn <= x <= xmx and zmn <= z <= zmx):
                    continue
                text = sign_text(be)
                stack = parse_range(text, stack_labels)
                rep = parse_range(text, rep_labels)
                if stack is not None:
                    stack_rng = stack
                    strip.append((x, y, z))
                if rep is not None:
                    appearance = rep
                    strip.append((x, y, z))
    return stack_rng, appearance, set(strip)


def extract_cuboid(cuboid, strip_signs):
    w = get_world()
    x0, x1, y0, y1, z0, z1 = cuboid
    cells = []
    for y in range(y0, y1 + 1):
        layer = []
        for z in range(z0, z1 + 1):
            row = []
            for x in range(x0, x1 + 1):
                name, props = w.block(x, y, z)
                base = name.split(":")[1]
                if base in MARKER_BLOCKS or (x, y, z) in strip_signs or "sign" in base:
                    name, props = "minecraft:air", None
                row.append(blockstate(name, props))
            layer.append(row)
        cells.append(layer)
    return cells


def write_schem(cells, path):
    write_sponge_schem_cells(cells, path, DATA_VERSION)


def remove_existing_schems():
    for filename in os.listdir(BUILDS_PROD_SCHEM):
        if filename.endswith(".schem"):
            os.remove(os.path.join(BUILDS_PROD_SCHEM, filename))


def run(*, logger=None, progress=None):
    os.makedirs(BUILDS_PROD_SCHEM, exist_ok=True)
    remove_existing_schems()

    if progress is not None:
        progress(0, 1, "Scanning build regions...")
    builds = []
    for region in BUILD_TYPES:
        build_type = region.build_type
        (start_xyz, end_xyz) = region.bounds.as_tuple()
        xa, y0, za = start_xyz
        xb, y1, zb = end_xyz
        detected, skipped = detect_builds(build_type, xa, xb, za, zb, y0, y1)
        builds.extend(detected)
        if logger is not None:
            logger(f"type {build_type} region: {len(detected)} builds from wool boundaries")
        for xmn, zmn, reason in skipped:
            if logger is not None:
                logger(f"  !! boundary at x={xmn} z={zmn}: {reason} -- SKIPPED")

    catalog = {}
    total = len(builds)
    for i, (build_type, origin, size, cuboids, ground_y, boundary) in enumerate(builds):
        key = f"{i + 1:03d}"
        x0, x1, z0, z1 = boundary
        stack_rng, appearance, strip = catalog_signs(x0, x1, z0, z1)

        first_y0 = cuboids[0][2]
        entry = {"type": build_type, "size": size, "origin": origin, "ground_offset": ground_y - first_y0, "pieces": {}}
        if build_type == 1:
            write_schem(extract_cuboid(cuboids[0], strip), os.path.join(BUILDS_PROD_SCHEM, f"{key}.schem"))
            entry["pieces"]["whole"] = cuboids[0][3] - cuboids[0][2] + 1
        else:
            entry["stack"] = stack_rng if stack_rng is not None else [1, 1]
            entry["appearance"] = appearance if appearance is not None else [1, 1]
            for name, cuboid in zip(("bottom", "middle", "top"), cuboids):
                write_schem(extract_cuboid(cuboid, strip), os.path.join(BUILDS_PROD_SCHEM, f"{key}_{name}.schem"))
                entry["pieces"][name] = cuboid[3] - cuboid[2] + 1
        catalog[key] = entry
        if logger is not None:
            logger(f"extracted {key}")
        if progress is not None:
            progress(i + 1, total, key)

    json.dump(catalog, open(CATALOG, "w"), indent=2)
    if logger is not None:
        logger(f"wrote {len(catalog)} builds to {CATALOG}")
    return {"count": len(catalog), "catalog_path": CATALOG, "items": sorted(catalog)}


def main():
    run(logger=print)


if __name__ == "__main__":
    main()
