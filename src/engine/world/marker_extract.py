"""Marker-based asset extraction from a Minecraft world.

Road tiles, fill props, and buildings all use direct gold/diamond marker pairs:
one pair exports a whole asset, and three vertically aligned pairs export
bottom/middle/top pieces. The emerald next to the bottom gold marks ground level,
and the sign above that emerald carries the asset metadata.
"""

from __future__ import annotations

import json
import re
from collections import Counter, deque
from dataclasses import dataclass

from nbtlib import Compound

from engine.schematic.transform import BlockEntity
from engine.schematic.writer import blockstate

MARKER_BLOCKS = {"gold_block", "diamond_block", "emerald_block"}
MARKER_BLOCK_NAMES = {f"minecraft:{name}" for name in MARKER_BLOCKS}
# Chunk block-entity keys that describe position/identity rather than payload.
_BE_META_KEYS = ("id", "x", "y", "z", "keepPacked")


@dataclass(frozen=True)
class AssetComponent:
    origin: list        # [footprint_x0, footprint_z0, box_y0]
    size: list          # [width, depth] in blocks
    cuboids: list       # list of (x0, x1, y0, y1, z0, z1)
    ground_y: int       # emerald marker Y (ground level)
    boundary: tuple     # wool bounding box (xmn, xmx, zmn, zmx)


@dataclass(frozen=True)
class MarkerAssetComponent:
    origin: list        # [footprint_x0, footprint_z0, lowest_box_y0]
    size: list          # [width, depth] in blocks
    cuboids: list       # one cuboid or bottom/middle/top cuboids
    ground_offset: int  # emerald marker Y relative to the lowest cuboid bottom
    emerald: tuple      # emerald marker paired with the bottom gold
    boundary: tuple     # footprint box (xmn, xmx, zmn, zmx)


def block_base(world, x, y, z):
    return world.block(x, y, z)[0].split(":")[1]


def wool_boundary_components(world, x_a, x_b, z_a, z_b, y0, y1, *, on_progress=None):
    xlo, xhi = min(x_a, x_b), max(x_a, x_b)
    zlo, zhi = min(z_a, z_b), max(z_a, z_b)
    cx_lo, cx_hi = xlo >> 4, xhi >> 4
    cz_lo, cz_hi = zlo >> 4, zhi >> 4
    total_chunks = (cx_hi - cx_lo + 1) * (cz_hi - cz_lo + 1)
    chunks_done = 0
    occ = set()
    for cx in range(cx_lo, cx_hi + 1):
        x_start = max(xlo, cx << 4)
        x_end = min(xhi, (cx << 4) + 15)
        for cz in range(cz_lo, cz_hi + 1):
            z_start = max(zlo, cz << 4)
            z_end = min(zhi, (cz << 4) + 15)
            if not world.is_chunk_empty(cx, cz):
                for x in range(x_start, x_end + 1):
                    for z in range(z_start, z_end + 1):
                        if any(block_base(world, x, y, z).endswith("wool") for y in range(y0, y1 + 1)):
                            occ.add((x, z))
            chunks_done += 1
            if on_progress is not None:
                on_progress(chunks_done, total_chunks)

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


def _cuboid_from_pair(gold, diamond):
    x0, x1 = sorted((gold[0], diamond[0]))
    y0, y1 = sorted((gold[1], diamond[1]))
    z0, z1 = sorted((gold[2], diamond[2]))
    return x0, x1, y0, y1, z0, z1


def marker_blocks_in_region(world, x_a, x_b, z_a, z_b, y_range, *, on_progress=None):
    """Find gold/diamond/emerald asset markers directly in the configured region."""
    xlo, xhi = min(x_a, x_b), max(x_a, x_b)
    zlo, zhi = min(z_a, z_b), max(z_a, z_b)
    ylo, yhi = y_range
    cx_lo, cx_hi = xlo >> 4, xhi >> 4
    cz_lo, cz_hi = zlo >> 4, zhi >> 4
    sy_lo, sy_hi = ylo >> 4, yhi >> 4
    total_chunks = (cx_hi - cx_lo + 1) * (cz_hi - cz_lo + 1)
    chunks_done = 0
    found = {"gold_block": [], "diamond_block": [], "emerald_block": []}

    for cx in range(cx_lo, cx_hi + 1):
        for cz in range(cz_lo, cz_hi + 1):
            if not world.is_chunk_empty(cx, cz):
                for sy in range(sy_lo, sy_hi + 1):
                    for x, y, z, name in world.block_positions_in_section(cx, cz, sy, MARKER_BLOCK_NAMES):
                        if not (xlo <= x <= xhi and ylo <= y <= yhi and zlo <= z <= zhi):
                            continue
                        found[name.split(":")[-1]].append((x, y, z))
            chunks_done += 1
            if on_progress is not None:
                on_progress(chunks_done, total_chunks)

    for values in found.values():
        values.sort(key=lambda pos: (pos[2], pos[0], pos[1]))
    return found


def _diamond_faces_gold(diamond, gold):
    """A valid build diamond is north/west/up from its gold origin marker."""
    return diamond[0] <= gold[0] and diamond[1] >= gold[1] and diamond[2] <= gold[2]


def _nearby_horizontal_emerald(gold, emeralds):
    candidates = [
        emerald for emerald in emeralds
        if max(abs(emerald[0] - gold[0]), abs(emerald[2] - gold[2])) == 1
    ]
    return min(candidates, key=lambda pos: (pos[2], pos[0], pos[1])) if candidates else None


def pair_gold_diamond_markers(golds, diamonds):
    """Pair each gold marker with its closest unused north/west/up diamond."""
    unused = set(diamonds)
    cuboids = []
    skipped = []
    for gold in sorted(golds, key=lambda pos: (pos[2], pos[0], pos[1])):
        candidates = [diamond for diamond in unused if _diamond_faces_gold(diamond, gold)]
        if not candidates:
            skipped.append((gold[0], gold[2], f"no north/west/up diamond marker available for gold {gold}"))
            continue
        diamond = min(
            candidates,
            key=lambda pos: (
                (gold[0] - pos[0]) ** 2 + (gold[1] - pos[1]) ** 2 + (gold[2] - pos[2]) ** 2,
                pos[2],
                pos[0],
                pos[1],
            ),
        )
        unused.remove(diamond)
        cuboids.append((_cuboid_from_pair(gold, diamond), gold))
    for diamond in sorted(unused, key=lambda pos: (pos[2], pos[0], pos[1])):
        skipped.append((diamond[0], diamond[2], f"unused diamond marker {diamond}"))
    return cuboids, skipped


def group_marker_cuboids(cuboids, emeralds=()):
    """Group cuboids by vertical alignment into one- or three-layer assets."""
    grouped = {}
    for cuboid, gold in cuboids:
        x0, x1, _y0, _y1, z0, z1 = cuboid
        grouped.setdefault((x0, x1, z0, z1), []).append((cuboid, gold))

    components = []
    skipped = []
    for (x0, x1, z0, z1), group in sorted(grouped.items(), key=lambda item: (item[0][2], item[0][0])):
        group.sort(key=lambda item: (item[0][2], item[0][3], item[0][4], item[0][0]))
        if len(group) not in (1, 3):
            skipped.append((x0, z0, f"expected 1 or 3 vertically aligned layer(s), got {len(group)}"))
            continue
        bottom_cuboid, bottom_gold = group[0]
        emerald = _nearby_horizontal_emerald(bottom_gold, emeralds)
        if emerald is None:
            skipped.append((x0, z0, f"no horizontally adjacent emerald marker for gold {bottom_gold}"))
            continue
        ground_offset = emerald[1] - bottom_cuboid[2]
        ordered_cuboids = [cuboid for cuboid, _gold in group]
        y0 = min(bb[2] for bb in ordered_cuboids)
        components.append(MarkerAssetComponent(
            origin=[x0, z0, y0],
            size=[x1 - x0 + 1, z1 - z0 + 1],
            cuboids=ordered_cuboids,
            ground_offset=ground_offset,
            emerald=emerald,
            boundary=(x0, x1, z0, z1),
        ))
    return components, skipped


def detect_marker_assets(world, x_a, x_b, z_a, z_b, marker_y_range, *, on_progress=None):
    """Detect marker-authored assets from gold/diamond marker pairs.

    Each gold is paired with the closest unused diamond. The resulting cuboids are
    grouped by identical X/Z footprint, so three vertically aligned cuboids become
    a bottom/middle/top asset and a single cuboid becomes a whole asset.
    """
    markers = marker_blocks_in_region(
        world, x_a, x_b, z_a, z_b, marker_y_range, on_progress=on_progress
    )
    cuboids, skipped = pair_gold_diamond_markers(markers["gold_block"], markers["diamond_block"])
    components, group_skipped = group_marker_cuboids(cuboids, markers["emerald_block"])
    return components, skipped + group_skipped


BuildAssetComponent = MarkerAssetComponent
build_markers_in_region = marker_blocks_in_region
group_build_cuboids = group_marker_cuboids
detect_build_assets = detect_marker_assets


def detect_assets(world, x_a, x_b, z_a, z_b, y0, y1, expected_components, marker_y_range, *, on_progress=None):
    """Resolve every wool-bounded asset in the box into its marker cuboids.

    ``expected_components`` is 1 for a single solid (type-1 build, road, fill)
    or 3 for a stacked type-2 build. ``marker_y_range`` is the (lo, hi) Y span to
    search for markers -- kept independent of the box height so tall assets whose
    top corner rises above ``y1`` are still captured.
    """
    components, skipped = [], []
    for xmn, xmx, zmn, zmx in wool_boundary_components(world, x_a, x_b, z_a, z_b, y0, y1, on_progress=on_progress):
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


def _sign_line(raw):
    """Display text of one sign line, across the JSON, component, and plain forms."""
    text = str(raw)
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return text
    if isinstance(parsed, dict):
        return str(parsed.get("text", ""))
    if isinstance(parsed, str):
        return parsed
    return text


def sign_text(be):
    parts = []
    for side in ("front_text", "back_text"):
        for message in be.get(side, {}).get("messages", []):
            parts.append(_sign_line(message))
    return " ".join(part for part in parts if part)


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


def detect_source_ground_y(world, x_a, x_b, z_a, z_b):
    """Modal top-solid-block Y over the region -- the source world's ground plane.

    Assets are authored on a flat terrain surface, so the most common column top
    is that surface. Iterates chunks in the region and calls top_solid_blocks()
    once per chunk, independent of the stored heightmap (which can be stale after
    bulk block placement/import). Returns None when the region has no solid columns.

    This is the *source* ground (where assets are authored), distinct from the
    emerald marker's per-asset ``ground_y`` and the generated ``city_ground_y``.
    """
    xlo, xhi = min(x_a, x_b), max(x_a, x_b)
    zlo, zhi = min(z_a, z_b), max(z_a, z_b)
    cx_range = range(xlo >> 4, (xhi >> 4) + 1)
    cz_range = range(zlo >> 4, (zhi >> 4) + 1)
    tops = Counter()
    for cx in cx_range:
        for cz in cz_range:
            if world.is_chunk_empty(cx, cz):
                continue
            entries = world.top_solid_blocks(cx, cz)
            for col, entry in enumerate(entries):
                if entry is None:
                    continue
                bx = (cx << 4) + (col & 15)
                bz = (cz << 4) + (col >> 4)
                if xlo <= bx <= xhi and zlo <= bz <= zhi:
                    tops[entry[1]] += 1
    if not tops:
        return None
    # Assets (roads, builds) rise *above* the terrain, so the ground plane is the
    # lowest broadly-present surface -- not the mode, which in a road- or
    # build-dense region is the asset top. A level counts as ground when it
    # covers a meaningful share of columns, which filters stray holes/outliers.
    threshold = max(3, sum(tops.values()) // 20)  # ~5% of sampled columns
    common = [y for y, count in tops.items() if count >= threshold]
    return min(common) if common else tops.most_common(1)[0][0]


def ground_shift(world, x_a, x_b, z_a, z_b, reference_ground_y):
    """Y offset from ``reference_ground_y`` to this region's detected source ground.

    Added to the wool/marker search windows so extraction follows the world's
    actual ground plane. Returns 0 when the ground can't be detected, preserving
    the configured absolute windows.
    """
    ground = detect_source_ground_y(world, x_a, x_b, z_a, z_b)
    return 0 if ground is None else ground - reference_ground_y


def _cuboid_block_entities(world, cuboid):
    """BlockEntity records inside the cuboid, positioned relative to its origin.

    Signs, chests, banners, etc. carry their NBT (text, contents, patterns)
    verbatim; only their coordinates are made local. The gold/diamond/emerald
    markers live outside the extracted cuboid, so nothing here needs filtering.
    """
    x0, x1, y0, y1, z0, z1 = cuboid
    result = []
    for cx in range(x0 >> 4, (x1 >> 4) + 1):
        for cz in range(z0 >> 4, (z1 >> 4) + 1):
            chunk = world.load_chunk(cx, cz)
            if chunk is None:
                continue
            for be in chunk.get("block_entities", []):
                bx, by, bz = int(be["x"]), int(be["y"]), int(be["z"])
                if not (x0 <= bx <= x1 and y0 <= by <= y1 and z0 <= bz <= z1):
                    continue
                be_id = str(be.get("id", ""))
                if not be_id:
                    continue
                if ":" not in be_id:
                    be_id = f"minecraft:{be_id}"
                data = Compound({k: v for k, v in be.items() if k not in _BE_META_KEYS})
                result.append(BlockEntity(bx - x0, by - y0, bz - z0, be_id, data))
    return result


def extract_cuboid(world, cuboid, *, force_persistent_leaves=False):
    """Read a cuboid into (cells, block_entities), blanking marker blocks to air.

    Marker blocks (gold/diamond/emerald) are blanked to air; signs and other
    block-entity blocks are kept, and their NBT is carried out as BlockEntity
    records (the authoring markers live outside the cuboid, so in-cuboid signs are
    real content).

    ``force_persistent_leaves`` rewrites grown leaves (``persistent=false``) to
    ``persistent=true`` so they do not decay after a paste: non-persistent leaves
    whose logs fall out of range vanish over ticks, degrading the build (cherry
    canopies are the usual casualty).
    """
    x0, x1, y0, y1, z0, z1 = cuboid
    cells = []
    for y in range(y0, y1 + 1):
        layer = []
        for z in range(z0, z1 + 1):
            row = []
            for x in range(x0, x1 + 1):
                name, props = world.block(x, y, z)
                base = name.split(":")[1]
                if base in MARKER_BLOCKS:
                    name, props = "minecraft:air", None
                elif force_persistent_leaves and base.endswith("leaves") \
                        and props and props.get("persistent") == "false":
                    props = {**props, "persistent": "true"}
                row.append(blockstate(name, props))
            layer.append(row)
        cells.append(layer)
    return cells, _cuboid_block_entities(world, cuboid)
