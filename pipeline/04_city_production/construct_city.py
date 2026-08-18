"""Assemble the full 3D city .schem: road grid + real builds in the lots.

Reuses engine.road_network (network), engine.road_schematic
(3D roads + rotation), and
engine.building_schematic (building piece assembly). For each placed build it
stacks the middle a random count within the build's `stack` range, rotates it
to face its road, and stamps it at ground level.
Output: ./seed_<n>.schem (render it with pipeline/04_city_production/render_city.py).
"""
import argparse
import json
import os
import random
import shutil
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)                                # shared engine modules, constants
from engine import building_schematic as B                    # noqa: E402
from engine import city_layout as C                           # noqa: E402
from engine import road_network as R                          # noqa: E402
from engine import road_schematic as RG                       # noqa: E402
from config.config_algo import DEFAULT_SEED                   # noqa: E402
from config.config_path import BUILD_CATALOG, CITY_PROD_SCHEM, GRID_PROD_SCHEM, WORLDEDIT_SCHEM  # noqa: E402
from config.config_render import CITY_GROUND_FILL_BLOCK, CITY_GROUND_Y  # noqa: E402
from engine.schematic_reader import decode_schem              # noqa: E402
from engine.schematic_transform import rot_tile                 # noqa: E402
from engine.schematic_writer import write_sponge_schem_grid     # noqa: E402

CB = R.CELL
META = json.load(open(BUILD_CATALOG))
BUILD_SNAP_DROP = 1
PLAYER_ANCHOR_MARGIN = 1


# ---------------------------------------------------------------- file output
def copy_city_to_worldedit(path, seed):
    os.makedirs(WORLDEDIT_SCHEM, exist_ok=True)
    dst = os.path.join(WORLDEDIT_SCHEM, f"seed_{seed}_city.schem")
    shutil.copy2(path, dst)
    print("copied", dst)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--fine", type=int, default=None,
                    help="fine grid edge in cells; default: match 03_grid_production/seed_<seed>.schem when present")
    ap.add_argument("--out", default=None, help="default: ./seed_<seed>.schem")
    ap.add_argument("--no-ground-fill", action="store_true",
                    help="leave empty non-road lot cells as air instead of filling with the configured ground block")
    args = ap.parse_args()
    out = args.out or os.path.join(CITY_PROD_SCHEM, f"seed_{args.seed}.schem")
    fine = args.fine
    if fine is None:
        grid_path = os.path.join(GRID_PROD_SCHEM, f"seed_{args.seed}.schem")
        if os.path.exists(grid_path):
            fine = decode_schem(grid_path)[0] // CB
        else:
            fine = R.FINE

    road_grid, road_pal, (span, Hr, _), nt = RG.build(fine, args.seed)
    net = R.gen_networks(args.seed)
    road_cells = net["road_cells"]
    lots = C.find_lots(road_cells)
    rules = C.PlacementRules()
    catalog = C.load_catalog(rules)
    place_rng = random.Random(args.seed * 7 + 1)
    rule_state = rules.new_state(place_rng)
    height_rng = random.Random(args.seed * 7 + 2)

    inst, placements = [], []
    placements = C.place_city(road_cells, lots, catalog, place_rng, rules, rule_state,
                              type2_frontage_cells=net["big_fine_cells"])
    max_below_ground = max(
        (max(0, int(META[bld.num].get("ground_offset", CITY_GROUND_Y)) - CITY_GROUND_Y)
         for bld, _facing, _rect in placements),
        default=0,
    )
    # Reserve one extra layer below the road deck so buildings can sit slightly lower
    # without clipping negative Y in the output schematic.
    city_ground_y = CITY_GROUND_Y + max_below_ground + BUILD_SNAP_DROP
    road_y0 = city_ground_y - CITY_GROUND_Y
    maxh = road_y0 + Hr
    out_span = span + PLAYER_ANCHOR_MARGIN
    for bld, facing, rect in placements:
        m = META[bld.num]
        n_mid = height_rng.randint(*m["stack"]) if C.catalog_type(m) == 2 else 0
        t = rot_tile(B.assemble(bld.num, n_mid, META), C.FACE_K[facing])
        px, pz = C.placement_origin(rect, facing, t.W, t.L, CB)
        px += PLAYER_ANCHOR_MARGIN
        pz += PLAYER_ANCHOR_MARGIN
        y0 = city_ground_y - int(m.get("ground_offset", CITY_GROUND_Y)) - BUILD_SNAP_DROP
        inst.append((t, px, pz, y0))
        maxh = max(maxh, y0 + t.H)
    C.validate_placements(road_cells, placements)

    master = {"minecraft:air": 0}
    for st in road_pal:
        master.setdefault(st, len(master))
    grid = np.zeros((maxh, out_span, out_span), dtype=np.int16)
    inv_road = {v: k for k, v in road_pal.items()}
    remap = np.array([master[inv_road[i]] for i in range(len(road_pal))], dtype=np.int16)
    grid[road_y0:road_y0 + Hr,
         PLAYER_ANCHOR_MARGIN:PLAYER_ANCHOR_MARGIN + span,
         PLAYER_ANCHOR_MARGIN:PLAYER_ANCHOR_MARGIN + span] = remap[road_grid]
    build_mask = np.zeros((out_span, out_span), dtype=bool)      # projected non-air build footprint
    for t, px, pz, y0 in inst:
        for y in range(t.H):
            gy = y0 + y
            if not (0 <= gy < maxh):
                continue
            for z in range(t.L):
                gz = pz + z
                if not (0 <= gz < out_span):
                    continue
                r = t.cells[y][z]
                for x in range(t.W):
                    st = r[x]
                    if st.startswith("minecraft:air"):
                        continue
                    gx = px + x
                    if not (0 <= gx < out_span):
                        continue
                    build_mask[gz, gx] = True
                    idx = master.get(st)
                    if idx is None:
                        idx = master[st] = len(master)
                    grid[gy, gz, gx] = idx

    fill_idx = master.get(CITY_GROUND_FILL_BLOCK)
    if fill_idx is None:
        fill_idx = master[CITY_GROUND_FILL_BLOCK] = len(master)
    if not args.no_ground_fill:
        for fy in range(R.FINE):
            for fx in range(R.FINE):
                if (fx, fy) in road_cells:
                    continue
                z0 = PLAYER_ANCHOR_MARGIN + fy * CB
                z1 = PLAYER_ANCHOR_MARGIN + (fy + 1) * CB
                x0 = PLAYER_ANCHOR_MARGIN + fx * CB
                x1 = PLAYER_ANCHOR_MARGIN + (fx + 1) * CB
                area = grid[city_ground_y, z0:z1, x0:x1]
                mask = (area == 0) & ~build_mask[z0:z1, x0:x1]
                area[mask] = fill_idx
    for y in range(city_ground_y + 1):
        grid[y, 0, 0] = fill_idx
    print(f"seed={args.seed}, fine={fine}: roads={nt} tiles, buildings={len(inst)}, "
          f"grid {out_span}x{maxh}x{out_span}, palette={len(master)}")
    write_sponge_schem_grid(
        grid,
        master,
        out,
        RG.DATA_VERSION,
        offset=(0, -(city_ground_y + 1), 0),
    )
    print("saved", out)
    copy_city_to_worldedit(out, args.seed)


if __name__ == "__main__":
    main()
