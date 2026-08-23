"""Prototype writer: turn a city ``.schem`` into a standalone void world.

The inverse of :mod:`engine.world.anvil_world_reader`. It slices the city voxel
grid into 16x16x16 sections, bit-packs each section's ``block_states`` the same
way the reader unpacks them, assembles chunk NBT + region files, and drops the
result into a copy of the bundled ``default_world`` with the generator emptied to
a void (so nothing is generated around the city -- everything outside the written
chunks is simply void air).

Scope is deliberately small: just place the city, leave the rest void. No
lighting is baked (``isLightOn`` is false so Minecraft relights on load) and no
terrain/structures are generated.
"""

from __future__ import annotations

import io
import os
import shutil
import struct
import time
import zlib

import numpy as np
import nbtlib
from nbtlib import Byte, Compound, Double, Float, Int, List, Long, LongArray, String

from config.path import DEFAULT_WORLD, GUI
from config.versions import HARD_FLOOR_DATA_VERSION, release_name_for
from engine.schematic.reader import (
    decode_schem_array,
    decode_schem_block_entities,
    decode_schem_offset,
)

# Standard overworld build range; heightmap values are stored relative to the
# world floor and Minecraft uses 9 bits per column for a 384-tall world.
MIN_WORLD_Y = -64
WORLD_HEIGHT = 384
HEIGHTMAP_BITS = (WORLD_HEIGHT).bit_length()  # 9

TARGET_GROUND_Y = 64  # world Y the city ground plane is seated at
AIR_NAMES = frozenset({"minecraft:air", "minecraft:cave_air", "minecraft:void_air"})

# Minecraft shows this in the save list; the app icon doubles as the world icon.
APP_ICON = os.path.join(GUI, "icons", "app-icon.png")
WORLD_ICON_SIZE = 64

# Coarse progress steps a world export reports (read, compose, encode, level, done).
WORLD_WRITE_STEPS = 4


def _noop(*_args, **_kwargs):
    pass


def parse_state(state):
    """Split ``name[prop=val,...]`` into (name, properties_dict_or_None)."""
    if "[" not in state:
        return state, None
    name, rest = state.split("[", 1)
    props = {}
    for pair in rest.rstrip("]").split(","):
        key, _, value = pair.partition("=")
        props[key] = value
    return name, props


def _palette_entry(state):
    name, props = parse_state(state)
    entry = Compound({"Name": String(name)})
    if props:
        entry["Properties"] = Compound({k: String(v) for k, v in props.items()})
    return entry


def _pack(indices, bits):
    """Bit-pack palette indexes into longs (no cross-long spill; MC 1.16+ layout).

    Inverse of ``anvil_world_reader._decode_palette_indexes``.
    """
    per_long = 64 // bits
    n_longs = (indices.size + per_long - 1) // per_long
    out = np.zeros(n_longs, dtype=np.uint64)
    for slot in range(per_long):
        chunk = indices[slot::per_long].astype(np.uint64)
        out[: chunk.size] |= chunk << np.uint64(slot * bits)
    return LongArray(out.view(np.int64).tolist())


def _section_block_states(local_idx, global_vals, inv):
    """Build a section ``block_states`` compound (air interned at index 0)."""
    palette = {"minecraft:air": 0}
    idx4096 = np.zeros(4096, dtype=np.int64)
    for local, gval in zip(local_idx, global_vals):
        state = inv[int(gval)]
        slot = palette.get(state)
        if slot is None:
            slot = palette[state] = len(palette)
        idx4096[local] = slot
    entries = [None] * len(palette)
    for state, slot in palette.items():
        entries[slot] = _palette_entry(state)
    block_states = Compound({"palette": List[Compound](entries)})
    if len(palette) > 1:
        bits = max(4, (len(palette) - 1).bit_length())
        block_states["data"] = _pack(idx4096, bits)
    return block_states


def _air_section(sy):
    return Compound({
        "Y": Byte(sy),
        "block_states": Compound({"palette": List[Compound]([_palette_entry("minecraft:air")])}),
        "biomes": Compound({"palette": List[String]([String("minecraft:plains")])}),
    })


def _pack_heightmap(heights):
    per_long = 64 // HEIGHTMAP_BITS
    n_longs = (256 + per_long - 1) // per_long
    out = np.zeros(n_longs, dtype=np.uint64)
    vals = heights.astype(np.uint64)
    for slot in range(per_long):
        chunk = vals[slot::per_long]
        out[: chunk.size] |= chunk << np.uint64(slot * HEIGHTMAP_BITS)
    return LongArray(out.view(np.int64).tolist())


def _chunk_nbt(cx, cz, sy_lo, sy_hi, sections_by_sy, heights, block_entities, data_version):
    sections = []
    for sy in range(sy_lo, sy_hi + 1):
        built = sections_by_sy.get(sy)
        if built is None:
            sections.append(_air_section(sy))
            continue
        local_idx, global_vals, inv = built
        sections.append(Compound({
            "Y": Byte(sy),
            "block_states": _section_block_states(local_idx, global_vals, inv),
            "biomes": Compound({"palette": List[String]([String("minecraft:plains")])}),
        }))
    hm = _pack_heightmap(np.clip(heights, 0, WORLD_HEIGHT))
    return Compound({
        "DataVersion": Int(data_version),
        "xPos": Int(cx),
        "zPos": Int(cz),
        "yPos": Int(sy_lo),
        "Status": String("minecraft:full"),
        "sections": List[Compound](sections),
        "block_entities": List[Compound](block_entities),
        "Heightmaps": Compound({
            "MOTION_BLOCKING": hm,
            "WORLD_SURFACE": hm,
        }),
        "isLightOn": Byte(0),
        "InhabitedTime": Long(0),
        "LastUpdate": Long(0),
    })


def _nbt_bytes(compound):
    f = nbtlib.File(compound)
    f.gzipped = False
    buf = io.BytesIO()
    f.write(buf)
    return buf.getvalue()


def _write_region(path, chunks):
    """Write an ``.mca`` region file from ``{(cx, cz): chunk_compound}``."""
    header = bytearray(8192)
    body = bytearray()
    next_sector = 2  # sectors 0-1 are the location + timestamp tables
    now = int(time.time())
    for (cx, cz), compound in chunks.items():
        raw = zlib.compress(_nbt_bytes(compound))
        payload = struct.pack(">I", len(raw) + 1) + bytes([2]) + raw
        pad = (-len(payload)) % 4096
        payload += b"\x00" * pad
        sector_count = len(payload) // 4096
        loc = (cx & 31) + (cz & 31) * 32
        struct.pack_into(">I", header, loc * 4, (next_sector << 8) | sector_count)
        struct.pack_into(">I", header, 4096 + loc * 4, now)
        body += payload
        next_sector += sector_count
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(header)
        fh.write(body)


def write_world(grid, inv, block_entities, out_dir, data_version, base_y, origin=None, spawn=None, source_world=None, progress=None):
    """Write ``grid`` (shape H,L,Z indexed [y][z][x]) as a void world at ``out_dir``.

    ``inv`` maps palette index -> block state string; ``block_entities`` are
    :class:`BlockEntity` records in schem-local coords. ``source_world`` is the
    world whose ``level.dat`` seeds the export (see :func:`_write_level_dat`).
    Returns a small summary.
    """
    progress = progress or _noop
    progress(1, WORLD_WRITE_STEPS, "Composing chunks")
    air_idx = np.array([i for i, s in inv.items() if s.split("[", 1)[0] in AIR_NAMES], dtype=grid.dtype)
    mask = ~np.isin(grid, air_idx) if air_idx.size else np.ones(grid.shape, bool)
    ys, zs, xs = np.nonzero(mask)
    if ys.size == 0:
        raise ValueError("schematic has no non-air blocks")
    vals = grid[ys, zs, xs]

    # Anchor a guaranteed-solid column (the one nearest the city centre) at the
    # world origin. Minecraft ignores the stored spawn in a flat/void world and
    # drops the player at 0,0,0, so we make 0,0,0 land on the city instead.
    anchor_x, anchor_z, anchor_top = _anchor_column(mask)
    if origin is None:
        origin = (-anchor_x, -anchor_z)

    wx = xs.astype(np.int64) + origin[0]
    wz = zs.astype(np.int64) + origin[1]
    wy = ys.astype(np.int64) + base_y
    cx, cz, sy = wx >> 4, wz >> 4, wy >> 4
    local = (wy & 15) * 256 + (wz & 15) * 16 + (wx & 15)

    sy_lo, sy_hi = int(sy.min()), int(sy.max())

    order = np.lexsort((sy, cz, cx))
    cx_o, cz_o, sy_o = cx[order], cz[order], sy[order]
    local_o, vals_o, wy_o = local[order], vals[order], wy[order]
    hm_col = ((wz[order] & 15) * 16 + (wx[order] & 15)).astype(np.intp)

    n = order.size
    chunk_break = np.empty(n, bool)
    chunk_break[0] = True
    chunk_break[1:] = (cx_o[1:] != cx_o[:-1]) | (cz_o[1:] != cz_o[:-1])
    starts = list(np.nonzero(chunk_break)[0]) + [n]

    regions = {}
    for i in range(len(starts) - 1):
        s, e = starts[i], starts[i + 1]
        ccx, ccz = int(cx_o[s]), int(cz_o[s])

        heights = np.full(256, MIN_WORLD_Y - 1, dtype=np.int64)
        np.maximum.at(heights, hm_col[s:e], wy_o[s:e])
        heights = heights - MIN_WORLD_Y + 1  # empty columns -> 0

        sec_sy = sy_o[s:e]
        sec_break = np.empty(e - s, bool)
        sec_break[0] = True
        sec_break[1:] = sec_sy[1:] != sec_sy[:-1]
        sec_starts = list(np.nonzero(sec_break)[0]) + [e - s]
        sections_by_sy = {}
        for j in range(len(sec_starts) - 1):
            a, b = sec_starts[j], sec_starts[j + 1]
            sections_by_sy[int(sec_sy[a])] = (local_o[s + a:s + b], vals_o[s + a:s + b], inv)

        be_list = _chunk_block_entities(block_entities, ccx, ccz, origin, base_y)
        compound = _chunk_nbt(ccx, ccz, sy_lo, sy_hi, sections_by_sy, heights, be_list, data_version)
        regions.setdefault((ccx >> 5, ccz >> 5), {})[(ccx, ccz)] = compound

    progress(2, WORLD_WRITE_STEPS, "Encoding regions")
    for (rx, rz), chunks in regions.items():
        _write_region(os.path.join(out_dir, "region", f"r.{rx}.{rz}.mca"), chunks)

    progress(3, WORLD_WRITE_STEPS, "Writing level.dat")
    if spawn is None:
        spawn = (anchor_x + origin[0], anchor_top + base_y + 1, anchor_z + origin[1])
    _write_level_dat(out_dir, data_version, spawn, source_world)
    _write_world_icon(out_dir)
    progress(WORLD_WRITE_STEPS, WORLD_WRITE_STEPS, "World saved")

    return {
        "out_dir": out_dir,
        "chunks": sum(len(c) for c in regions.values()),
        "regions": len(regions),
        "block_entities": len(block_entities),
    }


def _anchor_column(mask):
    """Return (x, z, surface_y) of the solid column nearest the city centre.

    ``mask`` is the (H, L, W) non-air mask indexed ``[y][z][x]``. The exact
    centre is often an empty gap in a void world, so we snap to the closest
    column that actually has ground.
    """
    _, length, width = mask.shape
    column = mask.any(axis=0)                       # (z, x) columns with any block
    zs, xs = np.nonzero(column)
    cz0, cx0 = length / 2.0, width / 2.0
    nearest = np.argmin((zs - cz0) ** 2 + (xs - cx0) ** 2)
    z, x = int(zs[nearest]), int(xs[nearest])
    surface_y = int(np.nonzero(mask[:, z, x])[0].max())
    return x, z, surface_y


def _chunk_block_entities(block_entities, cx, cz, origin, base_y):
    out = []
    for be in block_entities:
        wx, wy, wz = be.x + origin[0], be.y + base_y, be.z + origin[1]
        if wx >> 4 != cx or wz >> 4 != cz:
            continue
        entry = Compound({"id": String(be.id), "x": Int(wx), "y": Int(wy), "z": Int(wz)})
        for key, value in (be.data or {}).items():
            entry[key] = value
        out.append(entry)
    return out


def _write_world_icon(out_dir):
    """Copy the app icon in as the world's icon.png (64x64) for the save list."""
    if not os.path.exists(APP_ICON):
        return
    try:
        from PIL import Image
    except ImportError:
        return
    with Image.open(APP_ICON) as img:
        icon = img.convert("RGBA").resize((WORLD_ICON_SIZE, WORLD_ICON_SIZE), Image.LANCZOS)
        icon.save(os.path.join(out_dir, "icon.png"))


def _void_generator():
    """A flat generator with no layers -> a void dimension. Fresh Compound each call."""
    return Compound({
        "type": String("minecraft:flat"),
        "settings": Compound({
            "layers": List[Compound]([]),
            "biome": String("minecraft:the_void"),
            "features": Byte(0),
            "lakes": Byte(0),
            "structure_overrides": List[String]([]),
        }),
    })


def _void_world_gen_settings(seed):
    """A complete WorldGenSettings with every dimension a flat void.

    Fallback for the rare case where the base level.dat has no WorldGenSettings;
    normally we void the source world's own settings in place (see
    :func:`_write_level_dat`) to keep them native to the source version.
    """
    return Compound({
        "seed": Long(seed),
        "generate_features": Byte(0),
        "bonus_chest": Byte(0),
        "dimensions": Compound({
            "minecraft:overworld": Compound({"type": String("minecraft:overworld"), "generator": _void_generator()}),
            "minecraft:the_nether": Compound({"type": String("minecraft:the_nether"), "generator": _void_generator()}),
            "minecraft:the_end": Compound({"type": String("minecraft:the_end"), "generator": _void_generator()}),
        }),
    })


def _source_data_version(source_world):
    """The source world's own DataVersion (from its level.dat), or the floor."""
    if source_world:
        candidate = os.path.join(source_world, "level.dat")
        if os.path.isfile(candidate):
            try:
                return int(nbtlib.load(candidate)["Data"]["DataVersion"])
            except Exception:
                pass
    return HARD_FLOOR_DATA_VERSION


def _write_level_dat(out_dir, data_version, spawn, source_world):
    """Write the void-world level.dat from the source world's own level.dat.

    The source world (the one the user extracted from) already ships a level.dat
    native to its Minecraft version -- correct WorldGenSettings shape,
    enabled_features, data packs, everything. We reuse it and change only what a
    void city showcase needs, so the world loads natively (no DataFixer, block
    entities preserved exactly). Only the overworld *generator* is swapped to a
    flat void; the rest of WorldGenSettings (and the nether/end) is left exactly as
    the source authored it. Falls back to the bundled world's level.dat when the
    source's is unavailable.
    """
    src = os.path.join(source_world, "level.dat") if source_world else ""
    if not (src and os.path.isfile(src)):
        src = os.path.join(DEFAULT_WORLD, "level.dat")
    level = nbtlib.load(src)
    data = level["Data"]

    # Keep the source's native version; just ensure DataVersion and Version agree.
    data["DataVersion"] = Int(data_version)
    version = data.get("Version") or Compound({"Series": String("main")})
    version["Id"] = Int(data_version)
    version["Name"] = String(release_name_for(data_version))
    data["Version"] = version

    data["LevelName"] = String("CityGen City")
    data["GameType"] = Int(1)          # creative, to fly around the void city
    data["allowCommands"] = Byte(1)
    data["hardcore"] = Byte(0)         # don't inherit a hardcore source world
    data["initialized"] = Byte(1)
    data["Time"] = Long(6000)
    data["DayTime"] = Long(6000)       # midday
    data["raining"] = Byte(0)
    data["thundering"] = Byte(0)
    data["SpawnX"], data["SpawnY"], data["SpawnZ"] = Int(spawn[0]), Int(spawn[1]), Int(spawn[2])

    # Reset the world border so a small border on the source world isn't inherited.
    data["BorderCenterX"] = Double(0.0)
    data["BorderCenterZ"] = Double(0.0)
    data["BorderSize"] = Double(59999968.0)

    # A fresh, minimal player pinned to the spawn column. In singleplayer the saved
    # player position takes priority over the world spawn (and Minecraft ignores
    # SpawnY in a void world), so this is what actually lands the player on the
    # city. Building it fresh avoids carrying the source player's inventory or
    # position; Minecraft fills the rest with valid defaults for its version.
    data["Player"] = Compound({
        "Pos": List[Double]([Double(spawn[0] + 0.5), Double(spawn[1]), Double(spawn[2] + 0.5)]),
        "Motion": List[Double]([Double(0.0), Double(0.0), Double(0.0)]),
        "Rotation": List[Float]([Float(0.0), Float(0.0)]),
        "FallDistance": Float(0.0),
        "OnGround": Byte(1),
        "Dimension": String("minecraft:overworld"),
        "playerGameType": Int(1),
        "Health": Float(20.0),
        "foodLevel": Int(20),
    })

    # Void only the overworld generator, preserving the source's native
    # WorldGenSettings structure (its exact shape is version-specific). Everything
    # outside the written city chunks then generates as void air.
    wgs = data.get("WorldGenSettings")
    dims = wgs.get("dimensions") if wgs is not None else None
    if dims is not None and "minecraft:overworld" in dims:
        dims["minecraft:overworld"]["generator"] = _void_generator()
        if "generate_features" in wgs:
            wgs["generate_features"] = Byte(0)
    else:
        data["WorldGenSettings"] = _void_world_gen_settings(0)

    os.makedirs(out_dir, exist_ok=True)
    level.gzipped = True
    level.save(os.path.join(out_dir, "level.dat"))


def schem_to_world(schem_path, out_dir, source_world=None, data_version=None, progress=None):
    """Read a city ``.schem`` and write a standalone void world to ``out_dir``.

    The export is built from ``source_world``'s own ``level.dat`` and stamped at
    that world's native version, so it loads natively (no DataFixer, block entities
    preserved). ``source_world`` defaults to the bundled world. A stale world at
    ``out_dir`` is removed first so leftover region files from a previous, larger
    city can never survive into the export.
    """
    progress = progress or _noop
    progress(0, WORLD_WRITE_STEPS, "Reading schematic")
    _, height, length, inv, grid = decode_schem_array(schem_path)
    block_entities = decode_schem_block_entities(schem_path)
    offset = decode_schem_offset(schem_path)

    # Seat the city ground plane near TARGET_GROUND_Y. construct.py authors the
    # schem offset as -(city_ground_y + 1); recover it to place the ground nicely.
    city_ground_y = -offset[1] - 1
    base_y = TARGET_GROUND_Y - city_ground_y if offset[1] != 0 else TARGET_GROUND_Y

    # Match chunks + level.dat to the source world's own version (native load).
    if data_version is None:
        data_version = _source_data_version(source_world)

    shutil.rmtree(out_dir, ignore_errors=True)
    return write_world(grid, inv, block_entities, out_dir, data_version, base_y,
                       source_world=source_world, progress=progress)


if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    if __package__ in (None, ""):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    parser = argparse.ArgumentParser(description="Convert a city .schem into a standalone void world.")
    parser.add_argument("schem", help="path to a city .schem")
    parser.add_argument("out_dir", help="output world folder (created if missing)")
    args = parser.parse_args()

    summary = schem_to_world(args.schem, args.out_dir)
    print(f"wrote {summary['chunks']} chunks across {summary['regions']} region(s) to {summary['out_dir']}")
