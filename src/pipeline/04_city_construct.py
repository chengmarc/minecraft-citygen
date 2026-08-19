"""Assemble the full 3D city .schem: road grid + real builds in the lots."""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
from pathlib import Path

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.config_algo import DEFAULT_SEED, FINE as DEFAULT_FINE
from config.config_path import BUILD_CATALOG, CITY_PROD_SCHEM, GRID_PROD_SCHEM, WORLDEDIT_SCHEM
from config.config_render import CITY_GROUND_FILL_BLOCK, CITY_GROUND_Y
from engine import building_schematic as B
from engine import city_layout as C
from engine import road_network as R
from engine import road_schematic as RG
from engine.schematic_reader import decode_schem
from engine.schematic_transform import rot_tile
from engine.schematic_writer import write_sponge_schem_grid

CB = R.CELL
BUILD_SNAP_DROP = 1
PLAYER_ANCHOR_MARGIN = 1


def copy_city_to_worldedit(path, seed):
    os.makedirs(WORLDEDIT_SCHEM, exist_ok=True)
    dst = os.path.join(WORLDEDIT_SCHEM, f"seed_{seed}_city.schem")
    shutil.copy2(path, dst)
    return dst


def run(*, seed=DEFAULT_SEED, fine=None, out=None, no_ground_fill=False, logger=None):
    out = out or os.path.join(CITY_PROD_SCHEM, f"seed_{seed}.schem")
    if fine is None:
        grid_path = os.path.join(GRID_PROD_SCHEM, f"seed_{seed}.schem")
        if os.path.exists(grid_path):
            fine = decode_schem(grid_path)[0] // CB
        else:
            fine = DEFAULT_FINE

    size = R.make_size(fine)
    road_grid, road_pal, (span, Hr, _), nt = RG.build(fine, seed)
    net = R.gen_networks(seed, size=size)
    with open(BUILD_CATALOG, encoding="utf-8") as fh:
        meta = json.load(fh)
    road_cells = net["road_cells"]
    lots = C.find_lots(road_cells, size.fine)
    rules = C.PlacementRules()
    catalog = C.load_catalog(rules)
    place_rng = random.Random(seed * 7 + 1)
    rule_state = rules.new_state(place_rng)
    height_rng = random.Random(seed * 7 + 2)

    inst, placements = [], []
    placements = C.place_city(
        road_cells,
        lots,
        catalog,
        size.fine,
        place_rng,
        rules,
        rule_state,
        type2_frontage_cells=net["big_fine_cells"],
    )
    max_below_ground = max(
        (
            max(0, int(meta[placement.building.num].get("ground_offset", CITY_GROUND_Y)) - CITY_GROUND_Y)
            for placement in placements
        ),
        default=0,
    )
    city_ground_y = CITY_GROUND_Y + max_below_ground + BUILD_SNAP_DROP
    road_y0 = city_ground_y - CITY_GROUND_Y
    maxh = road_y0 + Hr
    out_span = span + PLAYER_ANCHOR_MARGIN
    for placement in placements:
        bld = placement.building
        facing = placement.facing
        rect = placement.rect
        m = meta[bld.num]
        n_mid = height_rng.randint(*m["stack"]) if C.catalog_type(m) == 2 else 0
        t = rot_tile(B.assemble(bld.num, n_mid, meta), C.FACE_K[facing])
        px, pz = C.placement_origin(rect, facing, t.W, t.L, CB)
        px += PLAYER_ANCHOR_MARGIN
        pz += PLAYER_ANCHOR_MARGIN
        y0 = city_ground_y - int(m.get("ground_offset", CITY_GROUND_Y)) - BUILD_SNAP_DROP
        inst.append((t, px, pz, y0))
        maxh = max(maxh, y0 + t.H)
    C.validate_placements(road_cells, placements, size.fine)

    master = {"minecraft:air": 0}
    for st in road_pal:
        master.setdefault(st, len(master))
    grid = np.zeros((maxh, out_span, out_span), dtype=np.int16)
    inv_road = {v: k for k, v in road_pal.items()}
    remap = np.array([master[inv_road[i]] for i in range(len(road_pal))], dtype=np.int16)
    grid[
        road_y0:road_y0 + Hr,
        PLAYER_ANCHOR_MARGIN:PLAYER_ANCHOR_MARGIN + span,
        PLAYER_ANCHOR_MARGIN:PLAYER_ANCHOR_MARGIN + span,
    ] = remap[road_grid]
    build_mask = np.zeros((out_span, out_span), dtype=bool)
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
    if not no_ground_fill:
        for fy in range(size.fine):
            for fx in range(size.fine):
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
    summary = (
        f"seed={seed}, fine={fine}: roads={nt} tiles, buildings={len(inst)}, "
        f"grid {out_span}x{maxh}x{out_span}, palette={len(master)}"
    )
    if logger is not None:
        logger(summary)
    write_sponge_schem_grid(grid, master, out, RG.DATA_VERSION, offset=(0, -(city_ground_y + 1), 0))
    if logger is not None:
        logger("saved", out)
    copied = None
    copy_error = None
    try:
        copied = copy_city_to_worldedit(out, seed)
    except OSError as exc:
        copy_error = str(exc)
        if logger is not None:
            logger("warning: could not copy to WorldEdit schematics folder:", copy_error)
    else:
        if logger is not None:
            logger("copied", copied)
    return {
        "output_path": out,
        "copied_path": copied,
        "copy_error": copy_error,
        "building_count": len(inst),
        "summary": summary,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument(
        "--fine",
        type=int,
        default=None,
        help="fine grid edge in cells; default: match the generated grid schematic for this seed when present",
    )
    ap.add_argument("--out", default=None, help="default: ./seed_<seed>.schem")
    ap.add_argument(
        "--no-ground-fill",
        action="store_true",
        help="leave empty non-road lot cells as air instead of filling with the configured ground block",
    )
    args = ap.parse_args()
    run(seed=args.seed, fine=args.fine, out=args.out, no_ground_fill=args.no_ground_fill, logger=print)


if __name__ == "__main__":
    main()
