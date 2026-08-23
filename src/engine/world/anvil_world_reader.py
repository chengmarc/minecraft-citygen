"""Minimal reader for modern Anvil worlds (the section block_states palette
format, MC 1.18+; the bundled default_world is 1.19.4).

Uses only the region container + the section block_states palette/data, so it
does not depend on anvil-parser's (outdated) block decoder.
"""
from __future__ import annotations

import gzip
import io
import os
import struct
import zlib

import numpy as np
import nbtlib

from config.path_discovery import region_dir_candidates
from config.config_world import REGION_DIR, REGION_DIR_CANDIDATES, SAVE


def _checked_region_paths(region_dir, save_path, fallback_candidates):
    checked = []
    if region_dir:
        checked.append(region_dir)
    for candidate in region_dir_candidates(save_path):
        if candidate not in checked:
            checked.append(candidate)
    if not checked:
        checked.extend(fallback_candidates)
    elif region_dir == REGION_DIR and save_path == SAVE:
        for candidate in fallback_candidates:
            if candidate not in checked:
                checked.append(candidate)
    return tuple(checked)


def _missing_region_dir_message(save_path, checked_paths):
    checked_lines = "\n".join(f"- {path}" for path in checked_paths) or "- <save>/region"
    return (
        "Minecraft world region directory not found.\n"
        f"Configured save: {save_path or '<not set>'}\n"
        "Checked:\n"
        f"{checked_lines}\n"
        "Set MC_CITY_SAVE to your world folder or paste it into the Extraction tab."
    )


class World:
    def __init__(self, region_dir=REGION_DIR, save_path=SAVE):
        self.region_dir = region_dir
        self.save_path = save_path
        self._chunks = {}          # (cx,cz) -> chunk nbt (or None)
        self._sections = {}        # (cx,cz,sy) -> (palette, decoded index array or None)
        self._regions = {}         # (rx,rz) -> region file bytes (or None if absent)
        if not os.path.isdir(self.region_dir):
            checked = _checked_region_paths(self.region_dir, self.save_path, REGION_DIR_CANDIDATES)
            raise FileNotFoundError(_missing_region_dir_message(self.save_path, checked))

    def _region_bytes(self, rx, rz):
        """Return the whole .mca file bytes for a region (cached), or None."""
        key = (rx, rz)
        if key in self._regions:
            return self._regions[key]
        path = f"{self.region_dir}/r.{rx}.{rz}.mca"
        data = None
        if os.path.exists(path):
            with open(path, "rb") as f:
                data = f.read()
        self._regions[key] = data
        return data

    @staticmethod
    def _decode_chunk_payload(raw, compression):
        decompressors = {
            1: gzip.decompress,
            2: zlib.decompress,
            3: lambda data: data,
        }
        try:
            return decompressors[compression](raw)
        except KeyError as exc:
            raise ValueError(f"Unsupported Anvil compression type: {compression}") from exc

    @staticmethod
    def _decode_palette_indexes(data, palette_size):
        longs = np.asarray(data, dtype=np.int64).view(np.uint64)
        bits = max(4, (palette_size - 1).bit_length())
        per_long = 64 // bits
        mask = np.uint64((1 << bits) - 1)
        i = np.arange(4096, dtype=np.intp)
        shifts = (i % per_long * bits).astype(np.uint64)
        return (longs[i // per_long] >> shifts & mask).tolist()

    @staticmethod
    def _block_properties(entry):
        props = entry.get("Properties")
        return {str(key): str(props[key]) for key in props} if props else None

    def load_chunk(self, cx, cz):
        """Return the parsed chunk NBT at chunk coords (cx, cz), or None if absent."""
        if (cx, cz) in self._chunks:
            return self._chunks[(cx, cz)]
        data = self._region_bytes(cx >> 5, cz >> 5)
        chunk = None
        if data is not None and len(data) >= 4096:
            loc = (cx & 31) + (cz & 31) * 32
            offset = struct.unpack_from(">I", data, loc * 4)[0] >> 8
            if offset:
                pos = offset * 4096
                length = struct.unpack_from(">I", data, pos)[0]
                comp = data[pos + 4]
                raw = data[pos + 5:pos + 4 + length]
                dec = self._decode_chunk_payload(raw, comp)
                chunk = nbtlib.File.parse(io.BytesIO(dec))
        self._chunks[(cx, cz)] = chunk
        return chunk

    def _section(self, cx, cz, sy):
        key = (cx, cz, sy)
        if key in self._sections:
            return self._sections[key]
        chunk = self.load_chunk(cx, cz)
        result = (None, None)
        if chunk is not None:
            for s in chunk.get("sections", []):
                if int(s["Y"]) == sy:
                    bs = s.get("block_states")
                    if bs is None:
                        break
                    palette = list(bs["palette"])
                    data = bs.get("data")
                    if data is None:
                        result = (palette, None)      # uniform section
                    else:
                        result = (palette, self._decode_palette_indexes(data, len(palette)))
                    break
        self._sections[key] = result
        return result

    _AIR_BLOCKS = frozenset({"minecraft:air", "minecraft:cave_air", "minecraft:void_air"})

    def block(self, x, y, z):
        """Return (name, properties_dict_or_None) or ('minecraft:air', None)."""
        cx, cz, sy = x >> 4, z >> 4, y >> 4
        palette, idx = self._section(cx, cz, sy)
        if palette is None:
            return ("minecraft:air", None)
        v = 0 if idx is None else idx[(y & 15) * 256 + (z & 15) * 16 + (x & 15)]
        entry = palette[v]
        return str(entry["Name"]), self._block_properties(entry)

    def surface_heightmap(self, cx, cz):
        """Return (heights, min_y) for the chunk's WORLD_SURFACE heightmap.

        ``heights`` is a 256-entry list indexed ``(z & 15) * 16 + (x & 15)`` giving
        the world Y of each column's highest non-air block (``None`` for an empty
        column). Returns ``(None, 0)`` when the chunk or heightmap is absent. This
        is how map tools stay fast: one array read replaces a per-column scan.
        """
        chunk = self.load_chunk(cx, cz)
        if chunk is None:
            return None, 0
        heightmaps = chunk.get("Heightmaps")
        section_ys = [int(s["Y"]) for s in chunk.get("sections", [])]
        if heightmaps is None or not section_ys:
            return None, 0
        data = heightmaps.get("WORLD_SURFACE")
        if data is None:
            return None, 0
        # The WORLD_SURFACE heightmap is encoded relative to the dimension's
        # minimum build height (-64 for 1.18+ overworld, section Y = -4), not
        # the chunk's lowest section. Clamp to -4 to skip spurious void sections
        # (e.g. Y=-5) that appear below the world floor in some generated worlds.
        min_y = max(min(section_ys), -4) * 16
        longs = np.asarray(data, dtype=np.int64).view(np.uint64)
        n = 256
        per_long = -(-n // len(longs))  # ceil: derive packing from longs count
        bits = 64 // per_long
        mask = np.uint64((1 << bits) - 1)
        i = np.arange(n, dtype=np.intp)
        shifts = (i % per_long * bits).astype(np.uint64)
        values = (longs[i // per_long] >> shifts & mask).tolist()
        heights = [None if v == 0 else min_y + v - 1 for v in values]
        return heights, min_y

    def is_chunk_empty(self, cx, cz):
        """Return True when the chunk is absent from the region file."""
        return self.load_chunk(cx, cz) is None

    def top_solid_blocks(self, cx, cz):
        """Return the highest non-air block for all 256 columns in a chunk.

        Returns a list of 256 entries indexed by ``z_local * 16 + x_local``.
        Each entry is ``(name, world_y)`` or ``None`` for empty columns.
        """
        chunk = self.load_chunk(cx, cz)
        if chunk is None:
            return [None] * 256
        section_ys = sorted([int(s["Y"]) for s in chunk.get("sections", [])], reverse=True)
        if not section_ys:
            return [None] * 256

        result = [None] * 256
        settled = np.zeros(256, dtype=bool)

        for sy in section_ys:
            if settled.all():
                break
            palette, idx = self._section(cx, cz, sy)
            if palette is None:
                continue
            names = [str(e["Name"]) for e in palette]
            if all(n in self._AIR_BLOCKS for n in names):
                continue
            is_air = np.array([n in self._AIR_BLOCKS for n in names], dtype=bool)

            if idx is None:
                world_y = (sy << 4) + 15
                for col in np.where(~settled)[0]:
                    result[col] = (names[0], world_y)
                settled[:] = True
                continue

            idx_arr = np.array(idx, dtype=np.int32).reshape(16, 256)
            for yy in range(15, -1, -1):
                if settled.all():
                    break
                col_idx = idx_arr[yy]
                solid = ~settled & ~is_air[col_idx]
                if solid.any():
                    world_y = (sy << 4) + yy
                    for col in np.where(solid)[0]:
                        result[col] = (names[col_idx[col]], world_y)
                    settled |= solid

        return result

    def top_solid_block(self, x, z):
        """Return (name, y, properties) of the highest non-air block in the column.

        Scans the full column from the top populated section downward, skipping
        empty/absent sections so it stays fast over a whole world. Returns None
        when the chunk is absent or the column holds no solid block.
        """
        cx, cz = x >> 4, z >> 4
        chunk = self.load_chunk(cx, cz)
        if chunk is None:
            return None
        section_ys = [int(s["Y"]) for s in chunk.get("sections", [])]
        if not section_ys:
            return None
        lx, lz = x & 15, z & 15
        for sy in range(max(section_ys), min(section_ys) - 1, -1):
            palette, idx = self._section(cx, cz, sy)
            if palette is None:
                continue
            if all(str(e["Name"]) in self._AIR_BLOCKS for e in palette):
                continue
            for yy in range(15, -1, -1):
                v = 0 if idx is None else idx[yy * 256 + lz * 16 + lx]
                entry = palette[v]
                name = str(entry["Name"])
                if name in self._AIR_BLOCKS:
                    continue
                return name, (sy << 4) + yy, self._block_properties(entry)
        return None
