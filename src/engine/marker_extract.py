"""Shared marker-based asset extraction from a Minecraft world.

Buildings, road tiles, and fill props are all authored in the world with the
*same* convention, so they share one geometry pass:

  * a wool rectangle bounds each asset (connected wool components separate them);
  * a gold + diamond pair marks two opposite corners of each solid cuboid;
  * a single emerald marks ground level (its Y seats the asset in the city).

The building extractor packages the result into a stacked catalog; the road /
fill extractor names each result from its sign. The logic below is common to
both and knows nothing about either domain.
"""

from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass

from engine.schematic_writer import blockstate

MARKER_BLOCKS = {"gold_block", "diamond_block", "emerald_block"}


@dataclass(frozen=True)
class AssetComponent:
    origin: list        # [footprint_x0, footprint_z0, box_y0]
    size: list          # [width, depth] in blocks
    cuboids: list       # list of (x0, x1, y0, y1, z0, z1)
    ground_y: int       # emerald marker Y (ground level)
    boundary: tuple     # wool bounding box (xmn, xmx, zmn, zmx)


def block_base(world, x, y, z):
    return world.block(x, y, z)[0].split(":")[1]


def wool_boundary_components(world, x_a, x_b, z_a, z_b, y0, y1):
    xlo, xhi = min(x_a, x_b), max(x_a, x_b)
    zlo, zhi = min(z_a, z_b), max(z_a, z_b)
    occ = set()
    for x in range(xlo, xhi + 1):
        for z in range(zlo, zhi + 1):
            if any(block_base(world, x, y, z).endswith("wool") for y in range(y0, y1 + 1)):
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


def markers_in_bounds(world, xmn, xmx, zmn, zmx, y_range):
    found = {kind: [] for kind in MARKER_BLOCKS}
    ylo, yhi = y_range
    for x in range(xmn, xmx + 1):
        for z in range(zmn, zmx + 1):
            for y in range(ylo, yhi + 1):
                base = block_base(world, x, y, z)
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


def detect_assets(world, x_a, x_b, z_a, z_b, y0, y1, expected_components, marker_y_range):
    """Resolve every wool-bounded asset in the box into its marker cuboids.

    ``expected_components`` is 1 for a single solid (type-1 build, road, fill)
    or 3 for a stacked type-2 build. ``marker_y_range`` is the (lo, hi) Y span to
    search for markers -- kept independent of the box height so tall assets whose
    top corner rises above ``y1`` are still captured.
    """
    components, skipped = [], []
    for xmn, xmx, zmn, zmx in wool_boundary_components(world, x_a, x_b, z_a, z_b, y0, y1):
        markers = markers_in_bounds(world, xmn, xmx, zmn, zmx, marker_y_range)
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
        components.append(AssetComponent(
            origin=[footprint_x0, footprint_z0, y0],
            size=[footprint_x1 - footprint_x0 + 1, footprint_z1 - footprint_z0 + 1],
            cuboids=cuboids,
            ground_y=emeralds[0][1],
            boundary=(xmn, xmx, zmn, zmx),
        ))
    return components, skipped


def sign_text(be):
    parts = []
    for side in ("front_text", "back_text"):
        for message in be.get(side, {}).get("messages", []):
            text = str(message)
            try:
                parsed = json.loads(text)
                text = parsed.get("text", text) if isinstance(parsed, dict) else text
            except (ValueError, TypeError):
                pass
            if text:
                parts.append(text)
    return " ".join(parts)


def iter_signs(world, x_a, x_b, z_a, z_b):
    """Yield (x, y, z, text) for every sign block-entity inside the XZ box."""
    xlo, xhi = min(x_a, x_b), max(x_a, x_b)
    zlo, zhi = min(z_a, z_b), max(z_a, z_b)
    for cx in range(xlo >> 4, (xhi >> 4) + 1):
        for cz in range(zlo >> 4, (zhi >> 4) + 1):
            chunk = world.load_chunk(cx, cz)
            if chunk is None:
                continue
            for be in chunk.get("block_entities", []):
                if "sign" not in str(be.get("id", "")):
                    continue
                x, y, z = int(be["x"]), int(be["y"]), int(be["z"])
                if xlo <= x <= xhi and zlo <= z <= zhi:
                    yield x, y, z, sign_text(be)


def parse_range(text, labels):
    for label in labels:
        pattern = rf"{label}\s*(\d+)(?:\s*-\s*(\d+))?"
        match = re.search(pattern, text, re.I)
        if match:
            lo = int(match.group(1))
            hi = int(match.group(2)) if match.group(2) else lo
            return [min(lo, hi), max(lo, hi)]
    return None


def extract_cuboid(world, cuboid):
    """Read a cuboid into schem cells, blanking marker blocks and signs to air."""
    x0, x1, y0, y1, z0, z1 = cuboid
    cells = []
    for y in range(y0, y1 + 1):
        layer = []
        for z in range(z0, z1 + 1):
            row = []
            for x in range(x0, x1 + 1):
                name, props = world.block(x, y, z)
                base = name.split(":")[1]
                if base in MARKER_BLOCKS or "sign" in base:
                    name, props = "minecraft:air", None
                row.append(blockstate(name, props))
            layer.append(row)
        cells.append(layer)
    return cells
