"""
Road network model -- generation and the tile catalogue, with no rendering.

`gen_networks()` builds the seeded network; `iter_placements()` says which tile
goes where. Stage 3 draws it (`engine.render.road_layout`) and Stage 4 stamps
it in blocks (`engine.schematic.road`).

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

from __future__ import annotations

import random
from dataclasses import dataclass

from config.algo import CELL

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


@dataclass(frozen=True)
class NetworkSize:
    fine: int
    coarse: int
    span: int


def make_size(fine):
    """Network dimensions; ``fine`` rounds down to even so coarse cells tile it."""
    fine = int(fine)
    fine -= fine % 2
    return NetworkSize(fine=fine, coarse=fine // 2, span=fine * CELL)


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


def rot_dir(d, k):
    return ORDER[(ORDER.index(d) + k) % 4]


def rot_ports(ports, k):
    return frozenset((rot_dir(d, k), size) for d, size in ports)


def _compile_tile_lookup(catalogue):
    lookup = {}
    for base, name in catalogue:
        for k in range(4):
            lookup.setdefault(rot_ports(base, k), (name, k))
    return lookup


TILES_BY_LAYER = {"big": BIG_TILES, "small": SMALL_TILES, "mixed": MIXED_TILES}


def iter_tile_catalogue():
    """Yield ``(layer, base_ports, tile_name)`` for every road tile, in layer order."""
    for layer, catalogue in TILES_BY_LAYER.items():
        for base, name in catalogue:
            yield layer, base, name


def tile_footprint(layer, base):
    """Fine-cell (cols, rows) of a tile in its base orientation.

    Big tiles are 2x2 and small tiles 1x1. A mixed tile is 1x2 along the big road
    it carries: 2 cells wide when the big road runs N-S, 2 tall when it runs E-W.
    """
    if layer == "big":
        return 2, 2
    if layer == "small":
        return 1, 1
    big_dirs = {direction for direction, size in base if size == "b"}
    return (2, 1) if big_dirs & {"N", "S"} else (1, 2)


_LOOKUP_BY_LAYER = {layer: _compile_tile_lookup(catalogue) for layer, catalogue in TILES_BY_LAYER.items()}


# ---------------------------------------------------------------- generation
def _net_size(net, size=None):
    return net["size"] if size is None else size


def _generate_avenues(rng, size, step, lo=2, hi=None):
    """Big avenues on the coarse grid, evenly spaced with a little jitter."""
    hi = size.coarse - 2 if hi is None else hi
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


def _generate_streets(band_iv, size, algo, lo=2, hi=None):
    """Small streets that keep clear of big bands and each other."""
    hi = size.fine - 2 if hi is None else hi
    kept = []
    for v in range(lo, hi + 1):
        if v // 2 in (0, size.coarse - 1):
            continue
        if any(_gap_to(v, a, b) < algo.gap_mixed for a, b in band_iv):
            continue
        if kept and v - kept[-1] < algo.gap_small:
            continue                       # keep streets from clumping
        kept.append(v)
    return kept


def _generate_big_network(rng, size, algo):
    # E-W avenues are padded vertically by choosing row positions away from
    # top/bottom. N-S avenues are padded horizontally by choosing column
    # positions away from left/right.
    pad = algo.pad_big
    big_rows = _generate_avenues(rng, size, algo.gap_big, lo=pad, hi=size.coarse - 1 - pad)
    big_cols = _generate_avenues(rng, size, algo.gap_big, lo=pad, hi=size.coarse - 1 - pad)
    big_rows_ext = {r: (0, size.coarse - 1) for r in big_rows}
    big_cols_ext = {c: (0, size.coarse - 1) for c in big_cols}

    _make_corners(rng, big_rows, big_cols, big_rows_ext, big_cols_ext, size.coarse, algo.n_big_corners)
    _make_tees(rng, [(big_rows_ext, big_rows, big_cols_ext, ()),
                     (big_cols_ext, big_cols, big_rows_ext, ())],
               size.coarse, algo.n_big_tees)
    return big_rows, big_cols, big_rows_ext, big_cols_ext


def _generate_small_network(rng, size, algo, big_rows, big_cols):
    band_row_iv = [(2 * r, 2 * r + 1) for r in big_rows]
    band_col_iv = [(2 * c, 2 * c + 1) for c in big_cols]
    # E-W streets are padded vertically by choosing row positions away from
    # top/bottom. N-S streets are padded horizontally by choosing column
    # positions away from left/right.
    pad = algo.pad_small
    small_rows = _generate_streets(band_row_iv, size, algo, lo=pad, hi=size.fine - 1 - pad)
    small_cols = _generate_streets(band_col_iv, size, algo, lo=pad, hi=size.fine - 1 - pad)

    # Small-street ends snap to a big corridor edge (mixed T) or a
    # perpendicular small street (small T).
    col_edges = sorted({2 * c - 1 for c in big_cols} | {2 * c + 2 for c in big_cols})
    row_edges = sorted({2 * r - 1 for r in big_rows} | {2 * r + 2 for r in big_rows})
    small_rows_ext = {r: (0, size.fine - 1) for r in small_rows}
    small_cols_ext = {c: (0, size.fine - 1) for c in small_cols}

    _make_corners(rng, small_rows, small_cols, small_rows_ext, small_cols_ext, size.fine, algo.n_small_corners)
    _make_tees(rng, [(small_rows_ext, small_rows, small_cols_ext, col_edges),
                     (small_cols_ext, small_cols, small_rows_ext, row_edges)],
               size.fine, algo.n_small_tees)
    return small_rows, small_cols, small_rows_ext, small_cols_ext


def gen_networks(seed, size, algo):
    """The seeded road network on a ``size`` grid, shaped by ``algo``'s road knobs."""
    rng = random.Random(seed)
    big_rows, big_cols, big_rows_ext, big_cols_ext = _generate_big_network(rng, size, algo)
    small_rows, small_cols, small_rows_ext, small_cols_ext = _generate_small_network(rng, size, algo, big_rows, big_cols)

    net = {
        "size": size,
        "big_rows": set(big_rows), "big_cols": set(big_cols),
        "big_rows_ext": big_rows_ext, "big_cols_ext": big_cols_ext,
        "small_rows": set(small_rows), "small_cols": set(small_cols),
        "small_rows_ext": small_rows_ext, "small_cols_ext": small_cols_ext,
    }
    _cache_road_cells(net, size)
    return net


def _on_lines(x, y, rows, cols, row_ext, col_ext):
    return ((y in rows and row_ext[y][0] <= x <= row_ext[y][1]) or
            (x in cols and col_ext[x][0] <= y <= col_ext[x][1]))


def _raw_big_node(net, cx, cy, size=None):
    size = _net_size(net, size)
    return (0 <= cx < size.coarse and 0 <= cy < size.coarse and
            _on_lines(cx, cy, net["big_rows"], net["big_cols"],
                      net["big_rows_ext"], net["big_cols_ext"]))


def _raw_small_node(net, fx, fy, size=None):
    size = _net_size(net, size)
    return (0 <= fx < size.fine and 0 <= fy < size.fine and
            _on_lines(fx, fy, net["small_rows"], net["small_cols"],
                      net["small_rows_ext"], net["small_cols_ext"]))


def _cache_road_cells(net, size=None):
    size = _net_size(net, size)
    big_cells = {(cx, cy) for cy in range(size.coarse) for cx in range(size.coarse)
                 if _raw_big_node(net, cx, cy, size)}
    big_fine_cells = {(2 * cx + dx, 2 * cy + dy)
                      for cx, cy in big_cells
                      for dx in (0, 1) for dy in (0, 1)}
    small_cells = {(fx, fy) for fy in range(size.fine) for fx in range(size.fine)
                   if _raw_small_node(net, fx, fy, size)}
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
    size = net["size"]
    for layer in layers:
        if layer == "big":
            for cy in range(size.coarse):
                for cx in range(size.coarse):
                    if big_node(net, cx, cy):
                        p = _placement("big", big_ports(net, cx, cy), cx * 2, cy * 2)
                        if p is not None:
                            yield p
        elif layer == "small":
            for fy in range(size.fine):
                for fx in range(size.fine):
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

