"""Shared city lot placement for simulation and production.

The generator is intentionally simple:
  - roads define legal/non-legal cells
  - buildings snap to the 9-block fine-cell grid
  - type-2 buildings are placed first along big-road frontage
  - type-1 buildings fill the remaining cells
  - landmarks are tried once each, largest footprint first
  - each type-1 frontage position picks randomly among the top fitting buildings
  - banned building IDs never enter the catalog
"""
from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from config.algo import (
    BANNED_BUILDINGS,
    CELL,
    LANDMARK_SPACING,
    TYPE1_TOP_FIT_CHOICES,
)

DIRS = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
FACE_K = {"S": 0, "W": 1, "N": 2, "E": 3}

# Independent random streams derived from one city seed. Preview and production
# must draw from the same stream for the same decision, or they diverge.
PLACEMENT_STREAM = 1
STACK_HEIGHT_STREAM = 2
FILLER_STREAM = 3


def seeded_rng(seed, stream):
    return random.Random(seed * 7 + stream)


@dataclass(slots=True)
class Building:
    num: str
    type: int
    width: int
    depth: int
    meta: dict[str, Any]
    fw: int = field(init=False)
    fd: int = field(init=False)
    area: int = field(init=False)
    score: int = field(init=False)

    def __post_init__(self) -> None:
        self.fw = math.ceil(self.width / CELL)
        self.fd = math.ceil(self.depth / CELL)
        self.area = self.fw * self.fd
        self.score = self.width * self.depth


@dataclass(frozen=True, slots=True)
class PlacementRect:
    x0: int
    y0: int
    cols: int
    rows: int

    def cells(self):
        return [(self.x0 + i, self.y0 + j) for i in range(self.cols) for j in range(self.rows)]


@dataclass(frozen=True, slots=True)
class CityPlacement:
    building: Building
    facing: str
    rect: PlacementRect


def normalize_building_id(value):
    if isinstance(value, int):
        return f"{value:03d}"
    text = str(value).strip()
    return f"{int(text):03d}" if text.isdigit() else text


def load_catalog(catalog_meta, banned_buildings=BANNED_BUILDINGS):
    """Placeable Buildings from raw ``buildings.json`` entries, best-scoring first."""
    banned = {normalize_building_id(value) for value in banned_buildings}
    buildings = []
    for num, meta in catalog_meta.items():
        if normalize_building_id(num) in banned:
            continue
        width, depth = meta["size"]
        buildings.append(Building(num, meta["type"], width, depth, meta))
    buildings.sort(key=lambda b: (b.score, b.area, b.fw, b.fd, b.num), reverse=True)
    return buildings


def footprint(cx, cy, facing, fw, fd):
    if facing == "N":
        return PlacementRect(cx, cy, fw, fd)
    if facing == "S":
        return PlacementRect(cx, cy - fd + 1, fw, fd)
    if facing == "E":
        return PlacementRect(cx - fd + 1, cy, fd, fw)
    return PlacementRect(cx, cy, fd, fw)


def rect_fits(avail, rect, fine):
    x0, y0, cols, rows = rect.x0, rect.y0, rect.cols, rect.rows
    if x0 < 0 or y0 < 0 or x0 + cols > fine or y0 + rows > fine:
        return False
    return all(p in avail for p in rect.cells())


def rect_distance(a, b):
    ax1 = a.x0 + a.cols - 1
    ay1 = a.y0 + a.rows - 1
    bx1 = b.x0 + b.cols - 1
    by1 = b.y0 + b.rows - 1
    dx = max(b.x0 - ax1, a.x0 - bx1, 0)
    dy = max(b.y0 - ay1, a.y0 - by1, 0)
    return max(dx, dy)


def landmark_spacing_allows(rect, placements, spacing):
    if spacing <= 0:
        return True
    return all(rect_distance(rect, placement.rect) >= spacing for placement in placements)


def placement_origin(rect, facing, width, depth, cell_size=CELL):
    x0, z0, cols, rows = rect.x0, rect.y0, rect.cols, rect.rows
    bx0, bz0 = x0 * cell_size, z0 * cell_size

    if facing == "S":
        pz = bz0 + rows * cell_size - depth
    elif facing == "N":
        pz = bz0
    else:
        pz = bz0 + (rows * cell_size - depth) // 2

    if facing == "E":
        px = bx0 + cols * cell_size - width
    elif facing == "W":
        px = bx0
    else:
        px = bx0 + (cols * cell_size - width) // 2

    return px, pz


def find_lots(road_cells, fine):
    n = fine
    seen = [[False] * n for _ in range(n)]
    lots = []
    for sy in range(n):
        for sx in range(n):
            if (sx, sy) in road_cells or seen[sy][sx]:
                continue
            q = deque([(sx, sy)])
            seen[sy][sx] = True
            cells = []
            while q:
                x, y = q.popleft()
                cells.append((x, y))
                for dx, dy in DIRS.values():
                    nx, ny = x + dx, y + dy
                    if (0 <= nx < n and 0 <= ny < n and
                            (nx, ny) not in road_cells and not seen[ny][nx]):
                        seen[ny][nx] = True
                        q.append((nx, ny))
            lots.append(cells)
    return lots


def sort_frontage(cells, facing):
    key = {"N": lambda c: (c[1], c[0]), "S": lambda c: (-c[1], c[0]),
           "E": lambda c: (-c[0], c[1]), "W": lambda c: (c[0], c[1])}[facing]
    return sorted(cells, key=key)


def frontage_runs(cells, road_cells, fine):
    """Return contiguous frontage runs, longest first."""
    n = fine
    cellset = set(cells)
    runs = []
    for facing, (dx, dy) in DIRS.items():
        frontage = [(x, y) for (x, y) in cellset
                    if 0 <= x + dx < n and 0 <= y + dy < n and
                    (x + dx, y + dy) in road_cells]
        groups = {}
        for x, y in frontage:
            key = y if facing in ("N", "S") else x
            groups.setdefault(key, []).append((x, y))
        for key, group in groups.items():
            group.sort(key=lambda c: c[0] if facing in ("N", "S") else c[1])
            run = []
            prev = None
            for cell in group:
                axis = cell[0] if facing in ("N", "S") else cell[1]
                if prev is not None and axis != prev + 1:
                    if run:
                        runs.append((facing, run))
                    run = []
                run.append(cell)
                prev = axis
            if run:
                runs.append((facing, run))

    def key(item):
        facing, run = item
        first = run[0]
        return (-len(run), first[1], first[0], facing)

    return sorted(runs, key=key)


def validate_placements(road_cells, placements, fine):
    n = fine
    occupied = {}
    errors = []
    for placement in placements:
        building = placement.building
        rect = placement.rect
        x0, y0, cols, rows = rect.x0, rect.y0, rect.cols, rect.rows
        if x0 < 0 or y0 < 0 or x0 + cols > n or y0 + rows > n:
            errors.append(f"{building.num} footprint out of bounds: {rect}")
            continue
        for cell in rect.cells():
            if cell in road_cells:
                errors.append(f"{building.num} footprint overlaps road cell: {cell}")
            prev = occupied.get(cell)
            if prev is not None:
                errors.append(f"{building.num} footprint overlaps {prev} at cell {cell}")
            occupied[cell] = building.num
    if errors:
        sample = "; ".join(errors[:10])
        more = "" if len(errors) <= 10 else f"; ... +{len(errors) - 10} more"
        raise ValueError(f"invalid city placements: {sample}{more}")


def place_from_points(avail, points, facing, candidates, chooser, top_fit_choices, fine):
    placed = []
    for x, y in points:
        if (x, y) not in avail:
            continue
        options = []
        for building in candidates:
            rect = footprint(x, y, facing, building.fw, building.fd)
            if rect_fits(avail, rect, fine):
                options.append((building, rect))
                if len(options) == top_fit_choices:
                    break
        if options:
            building, rect = chooser.choice(options)
            avail.difference_update(rect.cells())
            placed.append(CityPlacement(building, facing, rect))
    return placed


def place_type2(avail, frontage_cells, catalog, fine, landmark_spacing=LANDMARK_SPACING):
    """Place each type-2 landmark at most once, largest footprint first."""
    placed = []
    candidates = sorted(
        (b for b in catalog if b.type == 2),
        key=lambda b: (b.score, b.area, b.fw, b.fd, b.num),
        reverse=True,
    )
    for building in candidates:
        selected = None
        for facing, run in frontage_runs(avail, frontage_cells, fine):
            for x, y in run:
                if (x, y) not in avail:
                    continue
                rect = footprint(x, y, facing, building.fw, building.fd)
                if not rect_fits(avail, rect, fine):
                    continue
                if not landmark_spacing_allows(rect, placed, landmark_spacing):
                    continue
                selected = (facing, rect)
                break
            if selected is not None:
                break
        if selected is None:
            continue
        facing, rect = selected
        avail.difference_update(rect.cells())
        placed.append(CityPlacement(building, facing, rect))
    return placed


def place_type1(avail, road_cells, lots, catalog, chooser, fine):
    """Fill remaining lot frontage with type-1 buildings."""
    placed = []
    candidates = [b for b in catalog if b.type == 1]
    n = fine
    for lot in lots:
        lot_cells = set(lot)
        for facing, (dx, dy) in DIRS.items():
            frontage = [(x, y) for (x, y) in lot_cells
                        if (x, y) in avail and
                        0 <= x + dx < n and 0 <= y + dy < n and
                        (x + dx, y + dy) in road_cells]
            placed += place_from_points(avail, sort_frontage(frontage, facing), facing,
                                        candidates, chooser, TYPE1_TOP_FIT_CHOICES, fine)
    return placed


def place_city(road_cells, lots, catalog, fine, rng, type2_frontage_cells=None, landmark_spacing=LANDMARK_SPACING):
    """Place type-2 buildings by longest big-road frontage, then fill with type-1."""
    avail = {cell for lot in lots for cell in lot}
    type2_frontage_cells = road_cells if type2_frontage_cells is None else type2_frontage_cells
    placed = []
    placed += place_type2(avail, type2_frontage_cells, catalog, fine, landmark_spacing)
    placed += place_type1(avail, road_cells, lots, catalog, rng, fine)
    return placed


def plan_city(seed, net, catalog_meta):
    """Lots and validated building placements for one seeded road network.

    The single placement entry point for both the Stage 3 preview and the
    Stage 4 city build, so the preview always shows the city that gets built.
    """
    road_cells = net["road_cells"]
    fine = net["size"].fine
    lots = find_lots(road_cells, fine)
    placements = place_city(
        road_cells,
        lots,
        load_catalog(catalog_meta),
        fine,
        seeded_rng(seed, PLACEMENT_STREAM),
        type2_frontage_cells=net["big_fine_cells"],
    )
    validate_placements(road_cells, placements, fine)
    return lots, placements
