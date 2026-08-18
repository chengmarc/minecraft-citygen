"""Extract the 14 road builds from the world into Sponge v2 .schem files.

Clean tile only: the yellow/white wool marker edge and the label sign are
stripped, leaving the pure road (9x9 / 18x18 / 9x18).
"""
import json
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)  # shared modules live in the repo root
from engine.anvil_world_reader import World
from engine.schematic_writer import blockstate, sponge_schem_from_cells
from config.config_path import ROADS_PROD_SCHEM
from config.config_world import DATA_VERSION, ROAD_BOX

X0, X1, Z0, Z1, Y0, Y1 = ROAD_BOX
OUT = ROADS_PROD_SCHEM
MARKER = {"minecraft:yellow_wool", "minecraft:white_wool"}
# stripped from the exported tile: the wool registration layer/frame and the
# diamond_block copy-paste origin marker (both are in-world build aids only).
EXCLUDE = MARKER | {"minecraft:diamond_block"}

w = World()


def top_name(x, z):
    for y in range(Y1, Y0 - 1, -1):
        n, _ = w.block(x, y, z)
        if n != "minecraft:air":
            return n
    return "minecraft:air"


# ---- signs (name + position) --------------------------------------------------
def read_signs():
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


# ---- connected components of built columns ------------------------------------
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
        q = deque([start]); seen.add(start); cells = []
        while q:
            x, z = q.popleft(); cells.append((x, z))
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                p = (x + dx, z + dz)
                if p in occ and p not in seen:
                    seen.add(p); q.append(p)
        xs = [c[0] for c in cells]; zs = [c[1] for c in cells]
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
                shrink(); xmn, xmx, zmn, zmx = bb; changed = True
                break
    return bb


def y_extent(xmn, xmx, zmn, zmx):
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
    W = xmx - xmn + 1
    H = ymx - ymn + 1
    L = zmx - zmn + 1
    cells = []
    for ly in range(H):
        layer = []
        for lz in range(L):
            row = []
            for lx in range(W):
                name, props = w.block(xmn + lx, ymn + ly, zmn + lz)
                if "sign" in name or name in EXCLUDE:
                    name, props = "minecraft:air", None
                row.append(blockstate(name, props))
            layer.append(row)
        cells.append(layer)
    schem, palette = sponge_schem_from_cells(cells, DATA_VERSION)
    return schem, (W, H, L), len(palette)


def main():
    os.makedirs(OUT, exist_ok=True)
    signs = read_signs()
    comps = components()
    print(f"{len(signs)} signs, {len(comps)} components")
    results = []
    for bb in comps:
        xmn, xmx, zmn, zmx = bb
        matches = [s for s in signs if xmn <= s[0] <= xmx and zmn <= s[1] <= zmx]
        if not matches:
            print("  !! no sign for", bb); continue
        name = matches[0][2]
        clean = strip_markers([xmn, xmx, zmn, zmx])
        cxmn, cxmx, czmn, czmx = clean
        ymn, ymx = y_extent(cxmn, cxmx, czmn, czmx)
        f, dims, pal = build_schem(cxmn, cxmx, czmn, czmx, ymn, ymx)
        path = os.path.join(OUT, name + ".schem")
        f.gzipped = True
        f.save(path)
        print(f"extracted {name}", flush=True)
        results.append((name, dims, pal))
    for name, dims, pal in sorted(results):
        print(f"  {name:32} {dims[0]:2}x{dims[1]}x{dims[2]:2} (WxHxL)  palette={pal}")
    print(f"saved {len(results)} schematics to {OUT}")


if __name__ == "__main__":
    main()
