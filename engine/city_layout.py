"""Shared city lot placement for simulation and production.

The generator is intentionally simple:
  - roads define legal/non-legal cells
  - buildings snap to the 9-block fine-cell grid
  - type-2 buildings are placed first along big-road frontage
  - type-1 buildings fill the remaining cells
  - each frontage position picks randomly among the top fitting buildings
  - optional rule hooks can reject catalog items or candidate placements
"""
import json
import math
from collections import deque

from engine import road_network as R
from config.config_algo import (BANNED_BUILDINGS, CELL, TYPE1_TOP_FIT_CHOICES,
                                TYPE2_SAME_COARSE_SPAN, TYPE2_TOP_FIT_CHOICES)
from config.config_path import BUILD_CATALOG

CELL_BLOCKS = CELL
DIRS = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
FACE_K = {"S": 0, "W": 1, "N": 2, "E": 3}


class Building:
    __slots__ = ("num", "type", "fw", "fd", "area", "score", "meta")

    def __init__(self, num, building_type, width, depth, meta):
        self.num = num
        self.type = building_type
        self.fw = math.ceil(width / CELL_BLOCKS)
        self.fd = math.ceil(depth / CELL_BLOCKS)
        self.area = self.fw * self.fd
        self.score = width * depth
        self.meta = meta


def normalize_building_id(value):
    if isinstance(value, int):
        return f"{value:03d}"
    text = str(value).strip()
    return f"{int(text):03d}" if text.isdigit() else text


class PlacementRuleState:
    def __init__(self, type2_targets):
        self.counts = {}
        self.type2_targets = type2_targets
        self.type2_coarse_cells = {}


class PlacementRules:
    def __init__(self, banned_buildings=None):
        banned = BANNED_BUILDINGS if banned_buildings is None else banned_buildings
        self.banned_buildings = {normalize_building_id(v) for v in banned}
        self.type2_appearance_ranges = {}
        self.type2_same_coarse_span = max(1, int(TYPE2_SAME_COARSE_SPAN))

    def new_state(self, rng):
        targets = {}
        for num, rep in self.type2_appearance_ranges.items():
            lo, hi = rep
            targets[num] = rng.randint(lo, hi)
        return PlacementRuleState(targets)

    def prepare_catalog(self, buildings):
        self.type2_appearance_ranges = {}
        for building in buildings:
            if building.type != 2:
                continue
            rep = building.meta.get("appearance", [1, 1])
            lo, hi = rep if isinstance(rep, list) else [rep, rep]
            lo, hi = max(1, int(lo)), max(1, int(hi))
            self.type2_appearance_ranges[building.num] = [min(lo, hi), max(lo, hi)]

    def allow_building(self, num, _meta):
        return normalize_building_id(num) not in self.banned_buildings

    def can_place(self, building, _facing, rect, state):
        if building.type != 2:
            return True

        target = state.type2_targets.get(building.num, 1)
        if state.counts.get(building.num, 0) >= target:
            return False
        return not self._type2_repeats_nearby(building.num, rect, state)

    def record_placement(self, building, _facing, rect, state):
        state.counts[building.num] = state.counts.get(building.num, 0) + 1
        if building.type == 2:
            cells = state.type2_coarse_cells.setdefault(building.num, set())
            cells.update(coarse_cells_of_rect(rect))

    def _type2_repeats_nearby(self, num, rect, state):
        occupied = state.type2_coarse_cells.get(num)
        if not occupied:
            return False
        max_delta = self.type2_same_coarse_span - 1
        for cx, cy in coarse_cells_of_rect(rect):
            for ox, oy in occupied:
                if abs(cx - ox) <= max_delta and abs(cy - oy) <= max_delta:
                        return True
        return False


def catalog_type(meta):
    return meta["type"]


def load_catalog(rules=None):
    data = json.load(open(BUILD_CATALOG))
    buildings = []
    for num, meta in data.items():
        if rules is not None and not rules.allow_building(num, meta):
            continue
        width, depth = meta["size"]
        buildings.append(Building(num, catalog_type(meta), width, depth, meta))
    buildings.sort(key=lambda b: (b.score, b.area, b.fw, b.fd, b.num), reverse=True)
    if rules is not None:
        rules.prepare_catalog(buildings)
    return buildings


def footprint(cx, cy, facing, fw, fd):
    if facing == "N":
        return cx, cy, fw, fd
    if facing == "S":
        return cx, cy - fd + 1, fw, fd
    if facing == "E":
        return cx - fd + 1, cy, fd, fw
    return cx, cy, fd, fw


def cells_of(x0, y0, cols, rows):
    return [(x0 + i, y0 + j) for i in range(cols) for j in range(rows)]


def coarse_cells_of_rect(rect):
    x0, y0, cols, rows = rect
    x1, y1 = x0 + cols - 1, y0 + rows - 1
    return [(cx, cy)
            for cx in range(x0 // 2, x1 // 2 + 1)
            for cy in range(y0 // 2, y1 // 2 + 1)]


def placement_origin(rect, facing, width, depth, cell_size=CELL_BLOCKS):
    x0, z0, cols, rows = rect
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


def find_lots(road_cells):
    n = R.FINE
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


def frontage_runs(cells, road_cells):
    """Return contiguous frontage runs, longest first."""
    n = R.FINE
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


def validate_placements(road_cells, placements):
    n = R.FINE
    occupied = {}
    errors = []
    for building, _facing, rect in placements:
        x0, y0, cols, rows = rect
        if x0 < 0 or y0 < 0 or x0 + cols > n or y0 + rows > n:
            errors.append(f"{building.num} footprint out of bounds: {rect}")
            continue
        for cell in cells_of(*rect):
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


def place_from_points(avail, points, facing, candidates, chooser, rules, rule_state,
                      top_fit_choices):
    placed = []
    n = R.FINE

    def fits(rect):
        x0, y0, cols, rows = rect
        if x0 < 0 or y0 < 0 or x0 + cols > n or y0 + rows > n:
            return False
        return all(p in avail for p in cells_of(*rect))

    def rules_allow(building, facing, rect):
        return rules is None or rules.can_place(building, facing, rect, rule_state)

    for x, y in points:
        if (x, y) not in avail:
            continue
        options = []
        for building in candidates:
            rect = footprint(x, y, facing, building.fw, building.fd)
            if fits(rect) and rules_allow(building, facing, rect):
                options.append((building, rect))
                if len(options) == top_fit_choices:
                    break
        if options:
            building, rect = chooser.choice(options)
            if rules is not None:
                rules.record_placement(building, facing, rect, rule_state)
            avail.difference_update(cells_of(*rect))
            placed.append((building, facing, rect))
    return placed


def place_type2(avail, frontage_cells, catalog, chooser, rules, rule_state):
    """Place type-2 buildings by longest uninterrupted big-road frontage."""
    placed = []
    candidates = [b for b in catalog if b.type == 2]
    for facing, run in frontage_runs(avail, frontage_cells):
        placed += place_from_points(avail, run, facing, candidates, chooser, rules, rule_state,
                                    TYPE2_TOP_FIT_CHOICES)
    return placed


def place_type1(avail, road_cells, lots, catalog, chooser, rules, rule_state):
    """Fill remaining lot frontage with type-1 buildings."""
    placed = []
    candidates = [b for b in catalog if b.type == 1]
    n = R.FINE
    for lot in lots:
        lot_cells = set(lot)
        for facing, (dx, dy) in DIRS.items():
            frontage = [(x, y) for (x, y) in lot_cells
                        if (x, y) in avail and
                        0 <= x + dx < n and 0 <= y + dy < n and
                        (x + dx, y + dy) in road_cells]
            placed += place_from_points(avail, sort_frontage(frontage, facing), facing,
                                        candidates, chooser, rules, rule_state,
                                        TYPE1_TOP_FIT_CHOICES)
    return placed


def place_city(road_cells, lots, catalog, rng=None, rules=None, rule_state=None,
               type2_frontage_cells=None):
    """Place type-2 buildings by longest big-road frontage, then fill with type-1."""
    avail = {cell for lot in lots for cell in lot}
    chooser = rng if rng is not None else R.random
    if rules is not None and rule_state is None:
        rule_state = rules.new_state(chooser)

    type2_frontage_cells = road_cells if type2_frontage_cells is None else type2_frontage_cells
    placed = []
    placed += place_type2(avail, type2_frontage_cells, catalog, chooser, rules, rule_state)
    placed += place_type1(avail, road_cells, lots, catalog, chooser, rules, rule_state)
    return placed
