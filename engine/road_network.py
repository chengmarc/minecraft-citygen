"""
Road grid library -- shared helper for the grid pipelines.

Holds network generation, the tile catalogue, and 2D vector compositing used by
03_grid_simulation/draw_grid.py (sim) and 03_grid_production/schematics/construct_grid.py
(prod). Not a driver itself -- import it, optionally call set_size(), then call
gen_networks()/compose().

Overlay model (big 2x2, small 1x1, mixed 1x2). Two independent Manhattan
networks are generated, then composited:

  * big network   : lives on the COARSE grid (1 coarse cell = 2x2 fine cells),
                    so big roads are 2-cell-wide corridors.
  * small network : lives on the FINE grid (1x1 cells).

Per fine cell the layers combine as:
    big only        -> big corridor
    small only      -> small road
    big AND small   -> MIXED.  A 1-wide small road crossing a 2-wide big
                       corridor overlaps exactly 2 fine cells, i.e. a 1x2
                       piece:  2x2(big) n 1x1(small) = 1x2(mixed).

Render order: big corridors, then mixed junctions overlaid on the crossed
half of a big tile, then pure small roads. The mixed art carries the same big
road through its centre as the big tile beneath it, so the overlay is seamless.

Two rules, both enforced by construction (see gen_networks):
  1. A small road never sits inside a big footprint except as a mixed crossing,
     so no small dead-end ever lands in the corner of a 2x2 big tile.
  2. A small road never runs collinear along a big corridor ("big wins"); the
     only overlaps are transverse crossings.
"""

import os
import random
from dataclasses import dataclass

from PIL import Image

from config_algo import (CELL, FINE, GAP_MIXED, GAP_BIG, GAP_SMALL, PAD_BIG, PAD_SMALL,
                         N_BIG_CORNERS, N_SMALL_CORNERS, N_BIG_TEES, N_SMALL_TEES)
from config_path import ROADS_SIM

# FINE/COARSE/SPAN are the live grid size. CELL/GAP_*/N_*_CORNERS are fixed
# tuning constants.
COARSE = FINE // 2    # coarse (big) grid
SPAN = FINE * CELL    # canvas edge, px

ASSET_DIR = ROADS_SIM   # sim pipeline: vector tiles

# direction unit vectors, clockwise from north
DIRS = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
ORDER = "NESW"


@dataclass(frozen=True)
class Placement:
    layer: str
    tile_name: str
    rotation: int
    fx: int
    fy: int
    ports: frozenset


def set_size(fine, *, even=False):
    """Set the live grid size and derived dimensions in one place."""
    global FINE, COARSE, SPAN
    FINE = int(fine)
    if even:
        FINE -= FINE % 2
    COARSE = FINE // 2
    SPAN = FINE * CELL
    return FINE


# ---------------------------------------------------------------- tile catalogue
# Each entry maps a base connection set -> asset name. A connection is
# (direction, size) with size "b" (big) or "s" (small). Any real orientation is
# obtained by rotating the base clockwise; the matcher rotates the PNG to suit.
BIG_TILES = [
    (frozenset({("N", "b"), ("S", "b")}), "02_big_2x2_I"),
    (frozenset({("N", "b"), ("S", "b"), ("E", "b"), ("W", "b")}), "05_big_2x2_X"),
    (frozenset({("S", "b"), ("E", "b"), ("W", "b")}), "04_big_2x2_T"),
    (frozenset({("N", "b"), ("E", "b")}), "03_big_2x2_L"),
    (frozenset({("S", "b")}), "01_big_2x2_deadend"),
]
SMALL_TILES = [
    (frozenset({("N", "s"), ("S", "s")}), "07_small_1x1_I"),
    (frozenset({("S", "s"), ("E", "s"), ("W", "s")}), "09_small_1x1_T"),
    (frozenset({("N", "s"), ("S", "s"), ("E", "s"), ("W", "s")}), "10_small_1x1_X"),
    (frozenset({("S", "s")}), "06_small_1x1_deadend"),
    (frozenset({("N", "s"), ("E", "s")}), "08_small_1x1_L"),
]
MIXED_TILES = [
    (frozenset({("S", "s"), ("E", "b"), ("W", "b")}), "13_mix_1x2_T_big_main"),
    (frozenset({("S", "b"), ("E", "s"), ("W", "s")}), "12_mix_1x2_T_small_main"),
    (frozenset({("N", "b"), ("S", "b"), ("E", "s"), ("W", "s")}), "14_mix_1x2_X"),
    (frozenset({("N", "b"), ("E", "s")}), "11_mix_1x2_L"),
]


def load_assets():
    assets = {}
    for _, name in BIG_TILES + SMALL_TILES + MIXED_TILES:
        assets[name] = Image.open(os.path.join(ASSET_DIR, name + ".png")).convert("RGBA")
    return assets


def rot_dir(d, k):
    return ORDER[(ORDER.index(d) + k) % 4]


def rot_ports(ports, k):
    return frozenset((rot_dir(d, k), size) for d, size in ports)


def rot_img(img, k):
    for _ in range(k % 4):
        img = img.transpose(Image.Transpose.ROTATE_270)  # 90 deg clockwise
    return img


def _compile_tile_lookup(catalogue):
    lookup = {}
    for base, name in catalogue:
        for k in range(4):
            lookup.setdefault(rot_ports(base, k), (name, k))
    return lookup


BIG_TILE_LOOKUP = _compile_tile_lookup(BIG_TILES)
SMALL_TILE_LOOKUP = _compile_tile_lookup(SMALL_TILES)
MIXED_TILE_LOOKUP = _compile_tile_lookup(MIXED_TILES)
_LOOKUP_BY_CATALOGUE = {
    id(BIG_TILES): BIG_TILE_LOOKUP,
    id(SMALL_TILES): SMALL_TILE_LOOKUP,
    id(MIXED_TILES): MIXED_TILE_LOOKUP,
}
_LOOKUP_BY_LAYER = {
    "big": BIG_TILE_LOOKUP,
    "small": SMALL_TILE_LOOKUP,
    "mixed": MIXED_TILE_LOOKUP,
}


def choose_tile(catalogue, target):
    """Return (asset name, clockwise rotations) for `target`, or None."""
    lookup = _LOOKUP_BY_CATALOGUE.get(id(catalogue))
    if lookup is None:
        lookup = _compile_tile_lookup(catalogue)
    return lookup.get(target)


# ---------------------------------------------------------------- generation
def _generate_avenues(rng, lo=2, hi=None, step=GAP_BIG):
    """Big avenues on the coarse grid, evenly spaced with a little jitter."""
    hi = COARSE - 2 if hi is None else hi
    base = sorted({min(hi, max(lo, a + rng.randint(-1, 1)))
                   for a in range(lo, hi + 1, step)})
    out = []
    for a in base:
        if not out or a - out[-1] >= 2:
            out.append(a)
    return out


def _make_tees(rng, specs, size, count):
    """Truncate full-span lines into real T-intersections."""
    full = (0, size - 1)
    span_min = size * 2 // 5
    cands = [(own, line, perp, extra)
             for own, lines, perp, extra in specs for line in lines]
    rng.shuffle(cands)
    made = 0
    for own, line, perp, extra in cands:
        if made >= count:
            break
        if own[line] != full:                     # already a corner/tee
            continue
        for stops in ([q for q in perp if perp[q] == full],
                      list(perp) + list(extra)):
            inner = [s for s in stops if 0 < s < size - 1]
            options = ([(s, "lo") for s in inner if s <= size - 1 - span_min] +
                       [(s, "hi") for s in inner if s >= span_min])
            if options:
                s, end = rng.choice(options)
                own[line] = (s, size - 1) if end == "lo" else (0, s)
                made += 1
                break
    return made


def _make_corners(rng, rows, cols, rows_ext, cols_ext, size, count):
    """Force L-corners by terminating a row and a column at their intersection."""
    rs = [r for r in rows if 3 <= r <= size - 4]
    cs = [c for c in cols if 3 <= c <= size - 4]
    rng.shuffle(rs)
    used_c, made = set(), 0
    for row in rs:
        if made >= count:
            break
        free = [c for c in cs if c not in used_c]
        if not free:
            break
        col = rng.choice(free)
        rows_ext[row] = (0, col) if rng.random() < 0.5 else (col, size - 1)
        cols_ext[col] = (0, row) if rng.random() < 0.5 else (row, size - 1)
        used_c.add(col)
        made += 1
    return made


def _gap_to(v, a, b):
    return 0 if a <= v <= b else (a - v if v < a else v - b)


def _generate_streets(band_iv, lo=2, hi=None):
    """Small streets that keep clear of big bands and each other."""
    hi = FINE - 2 if hi is None else hi
    kept = []
    for v in range(lo, hi + 1):
        if v // 2 in (0, COARSE - 1):
            continue
        if any(_gap_to(v, a, b) < GAP_MIXED for a, b in band_iv):
            continue
        if kept and v - kept[-1] < GAP_SMALL:
            continue                       # keep streets from clumping
        kept.append(v)
    return kept


def _generate_big_network(rng):
    # E-W avenues are padded vertically by choosing row positions away from
    # top/bottom. N-S avenues are padded horizontally by choosing column
    # positions away from left/right.
    big_rows = _generate_avenues(
        rng, lo=PAD_BIG, hi=COARSE - 1 - PAD_BIG)
    big_cols = _generate_avenues(
        rng, lo=PAD_BIG, hi=COARSE - 1 - PAD_BIG)
    big_rows_ext = {r: (0, COARSE - 1) for r in big_rows}
    big_cols_ext = {c: (0, COARSE - 1) for c in big_cols}

    _make_corners(rng, big_rows, big_cols, big_rows_ext, big_cols_ext,
                  COARSE, N_BIG_CORNERS)
    _make_tees(rng, [(big_rows_ext, big_rows, big_cols_ext, ()),
                     (big_cols_ext, big_cols, big_rows_ext, ())],
               COARSE, N_BIG_TEES)
    return big_rows, big_cols, big_rows_ext, big_cols_ext


def _generate_small_network(rng, big_rows, big_cols):
    band_row_iv = [(2 * r, 2 * r + 1) for r in big_rows]
    band_col_iv = [(2 * c, 2 * c + 1) for c in big_cols]
    # E-W streets are padded vertically by choosing row positions away from
    # top/bottom. N-S streets are padded horizontally by choosing column
    # positions away from left/right.
    small_rows = _generate_streets(
        band_row_iv, lo=PAD_SMALL, hi=FINE - 1 - PAD_SMALL)
    small_cols = _generate_streets(
        band_col_iv, lo=PAD_SMALL, hi=FINE - 1 - PAD_SMALL)

    # Small-street ends snap to a big corridor edge (mixed T) or a
    # perpendicular small street (small T).
    col_edges = sorted({2 * c - 1 for c in big_cols} | {2 * c + 2 for c in big_cols})
    row_edges = sorted({2 * r - 1 for r in big_rows} | {2 * r + 2 for r in big_rows})
    small_rows_ext = {r: (0, FINE - 1) for r in small_rows}
    small_cols_ext = {c: (0, FINE - 1) for c in small_cols}

    _make_corners(rng, small_rows, small_cols, small_rows_ext, small_cols_ext,
                  FINE, N_SMALL_CORNERS)
    _make_tees(rng, [(small_rows_ext, small_rows, small_cols_ext, col_edges),
                     (small_cols_ext, small_cols, small_rows_ext, row_edges)],
               FINE, N_SMALL_TEES)
    return small_rows, small_cols, small_rows_ext, small_cols_ext


def gen_networks(seed):
    rng = random.Random(seed)
    big_rows, big_cols, big_rows_ext, big_cols_ext = _generate_big_network(rng)
    small_rows, small_cols, small_rows_ext, small_cols_ext = _generate_small_network(
        rng, big_rows, big_cols)

    net = {
        "big_rows": set(big_rows), "big_cols": set(big_cols),
        "big_rows_ext": big_rows_ext, "big_cols_ext": big_cols_ext,
        "small_rows": set(small_rows), "small_cols": set(small_cols),
        "small_rows_ext": small_rows_ext, "small_cols_ext": small_cols_ext,
    }
    _cache_road_cells(net)
    return net


def _on_lines(x, y, rows, cols, row_ext, col_ext):
    return ((y in rows and row_ext[y][0] <= x <= row_ext[y][1]) or
            (x in cols and col_ext[x][0] <= y <= col_ext[x][1]))


def _raw_big_node(net, cx, cy):
    return (0 <= cx < COARSE and 0 <= cy < COARSE and
            _on_lines(cx, cy, net["big_rows"], net["big_cols"],
                      net["big_rows_ext"], net["big_cols_ext"]))


def _raw_small_node(net, fx, fy):
    return (0 <= fx < FINE and 0 <= fy < FINE and
            _on_lines(fx, fy, net["small_rows"], net["small_cols"],
                      net["small_rows_ext"], net["small_cols_ext"]))


def _cache_road_cells(net):
    big_cells = {(cx, cy) for cy in range(COARSE) for cx in range(COARSE)
                 if _raw_big_node(net, cx, cy)}
    big_fine_cells = {(2 * cx + dx, 2 * cy + dy)
                      for cx, cy in big_cells
                      for dx in (0, 1) for dy in (0, 1)}
    small_cells = {(fx, fy) for fy in range(FINE) for fx in range(FINE)
                   if _raw_small_node(net, fx, fy)}
    net["big_cells"] = big_cells
    net["big_fine_cells"] = big_fine_cells
    net["small_cells"] = small_cells
    net["road_cells"] = big_fine_cells | small_cells
    return net


# ---------------------------------------------------------------- topology queries
def big_node(net, cx, cy):
    return (cx, cy) in net["big_cells"]


def big_fine(net, fx, fy):
    return (fx, fy) in net["big_fine_cells"]


def small_node(net, fx, fy):
    return (fx, fy) in net["small_cells"]


def big_ports(net, cx, cy):
    ports = set()
    for d, (dx, dy) in DIRS.items():
        if big_node(net, cx + dx, cy + dy):
            ports.add((d, "b"))
    return frozenset(ports)


def small_on_axis(net, fx, fy, d):
    """Does the small street through (fx,fy) run along direction d?"""
    return (d in "EW" and fy in net["small_rows"]) or (d in "NS" and fx in net["small_cols"])


def small_ports(net, fx, fy):
    ports = set()
    for d, (dx, dy) in DIRS.items():
        nx, ny = fx + dx, fy + dy
        if big_fine(net, nx, ny):
            # feeds into a big corridor along its own axis -> mixed handles it,
            # but the small tile still needs a stub pointing that way
            if small_on_axis(net, fx, fy, d):
                ports.add((d, "s"))
        elif small_node(net, nx, ny):
            ports.add((d, "s"))
    return frozenset(ports)


def _placement(layer, ports, fx, fy):
    found = _LOOKUP_BY_LAYER[layer].get(ports)
    if found is None:
        return None
    tile_name, rotation = found
    return Placement(layer, tile_name, rotation, fx, fy, ports)


def _mixed_ports(net, block, arms):
    if not big_node(net, *block):                       # corridor present here?
        return None
    present = [(d, nb) for d, nb in arms if small_node(net, *nb)]
    if not present:                                     # street never reaches it
        return None
    ports = set(big_ports(net, *block))                 # the big through-road
    ports.update((d, "s") for d, _ in present)          # + the small crossbar
    return frozenset(ports)


def iter_placements(net, layers=("big", "mixed", "small")):
    """Yield tile placements for renderers, in the requested layer order."""
    for layer in layers:
        if layer == "big":
            for cy in range(COARSE):
                for cx in range(COARSE):
                    if big_node(net, cx, cy):
                        p = _placement("big", big_ports(net, cx, cy), cx * 2, cy * 2)
                        if p is not None:
                            yield p
        elif layer == "small":
            for fy in range(FINE):
                for fx in range(FINE):
                    if small_node(net, fx, fy) and not big_fine(net, fx, fy):
                        p = _placement("small", small_ports(net, fx, fy), fx, fy)
                        if p is not None:
                            yield p
        elif layer == "mixed":
            for fy in net["small_rows"]:        # E-W street x N-S avenue
                for cx in net["big_cols"]:
                    ports = _mixed_ports(
                        net, (cx, fy // 2),
                        [("E", (2 * cx + 2, fy)), ("W", (2 * cx - 1, fy))])
                    p = _placement("mixed", ports, 2 * cx, fy) if ports else None
                    if p is not None:
                        yield p
            for fx in net["small_cols"]:        # N-S street x E-W avenue
                for cy in net["big_rows"]:
                    ports = _mixed_ports(
                        net, (fx // 2, cy),
                        [("N", (fx, 2 * cy - 1)), ("S", (fx, 2 * cy + 2))])
                    p = _placement("mixed", ports, fx, 2 * cy) if ports else None
                    if p is not None:
                        yield p
        else:
            raise ValueError(f"unknown placement layer: {layer}")


# ---------------------------------------------------------------- render
def compose(net, assets):
    canvas = Image.new("RGBA", (SPAN, SPAN))
    for placement in iter_placements(net):
        img = rot_img(assets[placement.tile_name], placement.rotation)
        canvas.alpha_composite(img, (placement.fx * CELL, placement.fy * CELL))
    return canvas
