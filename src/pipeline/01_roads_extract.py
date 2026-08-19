"""Extract the 14 road builds from the world into Sponge v2 .schem files."""

from __future__ import annotations

import json
import os
import sys
from collections import deque
from functools import lru_cache
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.config_path import ROADS_PROD_SCHEM
from config.config_world import DATA_VERSION, ROAD_BOX
from engine.anvil_world_reader import World
from engine.schematic_writer import blockstate, sponge_schem_from_cells

(START_XYZ, END_XYZ) = ROAD_BOX.as_tuple()
X0, Y0, Z0 = START_XYZ
X1, Y1, Z1 = END_XYZ
OUT = ROADS_PROD_SCHEM
MARKER = {"minecraft:yellow_wool", "minecraft:white_wool"}
EXCLUDE = MARKER | {"minecraft:diamond_block"}


@lru_cache(maxsize=1)
def get_world():
    return World()


def top_name(x, z):
    w = get_world()
    for y in range(Y1, Y0 - 1, -1):
        n, _ = w.block(x, y, z)
        if n != "minecraft:air":
            return n
    return "minecraft:air"


def read_signs():
    w = get_world()
    out = []
    for cx in range(X0 >> 4, (X1 >> 4) + 1):
        for cz in range(Z0 >> 4, (Z1 >> 4) + 1):
            chunk = w._load_chunk(cx, cz)
            if chunk is None:
                continue
            for be in chunk.get("block_entities", []):
                if "sign" not in str(be.get("id", "")):
                    continue
                x, z = int(be["x"]), int(be["z"])
                if not (X0 <= x <= X1 and Z0 <= z <= Z1):
                    continue
                parts = []
                for side in ("front_text", "back_text"):
                    for m in be.get(side, {}).get("messages", []):
                        s = str(m)
                        try:
                            j = json.loads(s)
                            s = j.get("text", s) if isinstance(j, dict) else s
                        except Exception:
                            pass
                        parts.append(s.strip())
                name = "".join(parts).strip().replace(" ", "")
                if name:
                    out.append((x, z, name))
    return out


def components():
    occ = set()
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            if top_name(x, z) != "minecraft:air":
                occ.add((x, z))
    seen, comps = set(), []
    for start in occ:
        if start in seen:
            continue
        q = deque([start])
        seen.add(start)
        cells = []
        while q:
            x, z = q.popleft()
            cells.append((x, z))
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                p = (x + dx, z + dz)
                if p in occ and p not in seen:
                    seen.add(p)
                    q.append(p)
        xs = [c[0] for c in cells]
        zs = [c[1] for c in cells]
        comps.append([min(xs), max(xs), min(zs), max(zs)])
    return comps


def strip_markers(bb):
    xmn, xmx, zmn, zmx = bb
    changed = True
    while changed and xmx - xmn >= 1 and zmx - zmn >= 1:
        changed = False
        edges = {
            "W": ([(xmn, z) for z in range(zmn, zmx + 1)], lambda: bb.__setitem__(0, xmn + 1)),
            "E": ([(xmx, z) for z in range(zmn, zmx + 1)], lambda: bb.__setitem__(1, xmx - 1)),
            "N": ([(x, zmn) for x in range(xmn, xmx + 1)], lambda: bb.__setitem__(2, zmn + 1)),
            "S": ([(x, zmx) for x in range(xmn, xmx + 1)], lambda: bb.__setitem__(3, zmx - 1)),
        }
        for cells, shrink in edges.values():
            frac = sum(1 for (x, z) in cells if top_name(x, z) in MARKER) / len(cells)
            if frac >= 0.4:
                shrink()
                xmn, xmx, zmn, zmx = bb
                changed = True
                break
    return bb


def y_extent(xmn, xmx, zmn, zmx):
    w = get_world()
    ymin, ymax = None, None
    for x in range(xmn, xmx + 1):
        for z in range(zmn, zmx + 1):
            for y in range(Y0, Y1 + 1):
                n, _ = w.block(x, y, z)
                if n != "minecraft:air" and "sign" not in n and n not in EXCLUDE:
                    ymin = y if ymin is None else min(ymin, y)
                    ymax = y if ymax is None else max(ymax, y)
    return (ymin if ymin is not None else Y0), (ymax if ymax is not None else Y0)


def build_schem(xmn, xmx, zmn, zmx, ymn, ymx):
    w = get_world()
    width = xmx - xmn + 1
    height = ymx - ymn + 1
    length = zmx - zmn + 1
    cells = []
    for ly in range(height):
        layer = []
        for lz in range(length):
            row = []
            for lx in range(width):
                name, props = w.block(xmn + lx, ymn + ly, zmn + lz)
                if "sign" in name or name in EXCLUDE:
                    name, props = "minecraft:air", None
                row.append(blockstate(name, props))
            layer.append(row)
        cells.append(layer)
    schem, palette = sponge_schem_from_cells(cells, DATA_VERSION)
    return schem, (width, height, length), len(palette)


def remove_existing_schems():
    for filename in os.listdir(OUT):
        if filename.endswith(".schem"):
            os.remove(os.path.join(OUT, filename))


def run(*, logger=None, progress=None):
    os.makedirs(OUT, exist_ok=True)
    remove_existing_schems()
    signs = read_signs()
    comps = components()
    if logger is not None:
        logger(f"{len(signs)} signs, {len(comps)} components")
    results = []
    total = len(comps)
    completed = 0
    for bb in comps:
        xmn, xmx, zmn, zmx = bb
        matches = [s for s in signs if xmn <= s[0] <= xmx and zmn <= s[1] <= zmx]
        if not matches:
            if logger is not None:
                logger("  !! no sign for", bb)
            completed += 1
            if progress is not None:
                progress(completed, total, None)
            continue
        name = matches[0][2]
        clean = strip_markers([xmn, xmx, zmn, zmx])
        cxmn, cxmx, czmn, czmx = clean
        ymn, ymx = y_extent(cxmn, cxmx, czmn, czmx)
        f, dims, pal = build_schem(cxmn, cxmx, czmn, czmx, ymn, ymx)
        path = os.path.join(OUT, name + ".schem")
        f.gzipped = True
        f.save(path)
        if logger is not None:
            logger(f"extracted {name}")
        results.append((name, dims, pal))
        completed += 1
        if progress is not None:
            progress(completed, total, name)
    if not results:
        raise RuntimeError(
            "Road extraction found no assets in the configured region. "
            "Check the road bounds or the bundled default world content."
        )
    for name, dims, pal in sorted(results):
        if logger is not None:
            logger(f"  {name:32} {dims[0]:2}x{dims[1]}x{dims[2]:2} (WxHxL)  palette={pal}")
    if logger is not None:
        logger(f"saved {len(results)} schematics to {OUT}")
    return {"count": len(results), "output_dir": OUT, "items": [name for name, _dims, _pal in results]}


def main():
    run(logger=print)


if __name__ == "__main__":
    main()
