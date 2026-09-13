"""Minimal reader for modern Anvil worlds (the section block_states palette
format, MC 1.18+; the bundled default_world is 26.1.2).

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

from config.path import region_dir_candidates
from config.world import REGION_DIR, REGION_DIR_CANDIDATES, SAVE


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
        self._heightmaps = {}      # (cx,cz,key) -> decoded 256-entry height array
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
    _SURFACE_HEIGHTMAPS = ("WORLD_SURFACE", "WORLD_SURFACE_WG")

    def block(self, x, y, z):
        """Return (name, properties_dict_or_None) or ('minecraft:air', None)."""
        cx, cz, sy = x >> 4, z >> 4, y >> 4
        palette, idx = self._section(cx, cz, sy)
        if palette is None:
            return ("minecraft:air", None)
        v = 0 if idx is None else idx[(y & 15) * 256 + (z & 15) * 16 + (x & 15)]
        entry = palette[v]
        return str(entry["Name"]), self._block_properties(entry)

    def block_positions_in_section(self, cx, cz, sy, block_names):
        """Return world positions for target block names in one chunk section.

        This checks the raw section palette before decoding packed block-state
        indexes, so callers can skip whole sections that cannot contain the
        requested blocks.
        """
        targets = frozenset(str(name) for name in block_names)
        if not targets:
            return []
        chunk = self.load_chunk(cx, cz)
        if chunk is None:
            return []

        block_states = None
        for section in chunk.get("sections", []):
            if int(section["Y"]) == sy:
                block_states = section.get("block_states")
                break
        if block_states is None:
            return []

        raw_palette = list(block_states["palette"])
        names = [str(entry["Name"]) for entry in raw_palette]
        target_indexes = {
            index: name
            for index, name in enumerate(names)
            if name in targets
        }
        if not target_indexes:
            return []

        data = block_states.get("data")
        if data is None:
            name = target_indexes.get(0)
            if name is None:
                return []
            return [
                ((cx << 4) + lx, (sy << 4) + ly, (cz << 4) + lz, name)
                for ly in range(16)
                for lz in range(16)
                for lx in range(16)
            ]

        _palette, indexes = self._section(cx, cz, sy)
        if indexes is None:
            return []
        positions = []
        for offset, palette_index in enumerate(indexes):
            name = target_indexes.get(palette_index)
            if name is None:
                continue
            ly = offset >> 8
            remainder = offset & 255
            lz = remainder >> 4
            lx = remainder & 15
            positions.append(((cx << 4) + lx, (sy << 4) + ly, (cz << 4) + lz, name))
        return positions

    def is_chunk_empty(self, cx, cz):
        """Return True when the chunk is absent from the region file."""
        return self.load_chunk(cx, cz) is None

    @staticmethod
    def _chunk_min_y(chunk):
        y_pos = chunk.get("yPos")
        if y_pos is not None:
            return int(y_pos) << 4
        sections = chunk.get("sections", [])
        if not sections:
            raise ValueError("Chunk has no sections; cannot derive heightmap origin.")
        return min(int(section["Y"]) for section in sections) << 4

    @staticmethod
    def _chunk_height(chunk):
        sections = chunk.get("sections", [])
        if not sections:
            raise ValueError("Chunk has no sections; cannot derive heightmap bit width.")
        min_sy = min(int(section["Y"]) for section in sections)
        max_sy = max(int(section["Y"]) for section in sections)
        return (max_sy - min_sy + 1) << 4

    def _surface_heightmap_key(self, chunk):
        heightmaps = chunk.get("Heightmaps")
        if heightmaps is None:
            heightmaps = chunk.get("heightmaps")
        if heightmaps is None:
            return None
        for key in self._SURFACE_HEIGHTMAPS:
            if key in heightmaps:
                return key
        return None

    def _decode_heightmap(self, chunk, key):
        heightmaps = chunk.get("Heightmaps")
        if heightmaps is None:
            heightmaps = chunk.get("heightmaps")
        if heightmaps is None or key not in heightmaps:
            raise ValueError(f"Chunk is missing required {key} heightmap.")

        longs = np.asarray(heightmaps[key], dtype=np.int64).view(np.uint64)
        world_height = self._chunk_height(chunk)
        bits = max(1, world_height.bit_length())
        per_long = 64 // bits
        if per_long <= 0:
            raise ValueError(f"Invalid heightmap bit width: {bits}")

        indexes = np.arange(256, dtype=np.intp)
        required_longs = int((256 + per_long - 1) // per_long)
        if longs.size < required_longs:
            raise ValueError(f"{key} heightmap is truncated: expected {required_longs} longs, got {longs.size}.")

        shifts = (indexes % per_long * bits).astype(np.uint64)
        mask = np.uint64((1 << bits) - 1)
        return ((longs[indexes // per_long] >> shifts) & mask).astype(np.int32)

    def _heightmap_values(self, cx, cz, chunk, key):
        if not hasattr(self, "_heightmaps"):
            self._heightmaps = {}
        cache_key = (cx, cz, key)
        values = self._heightmaps.get(cache_key)
        if values is None:
            values = self._heightmaps[cache_key] = self._decode_heightmap(chunk, key)
        return values

    def heightmap_surface_blocks(self, cx, cz):
        """Return WORLD_SURFACE top blocks for all 256 columns in a chunk.

        Entries are indexed by ``z_local * 16 + x_local`` and each entry is
        ``(name, world_y)``. Absent chunks return all ``None`` entries; malformed
        generated chunks raise instead of falling back to a vertical scan.
        """
        chunk = self.load_chunk(cx, cz)
        if chunk is None:
            return [None] * 256

        min_y = self._chunk_min_y(chunk)
        heightmap_key = self._surface_heightmap_key(chunk)
        if heightmap_key is None:
            return [None] * 256
        heights = self._heightmap_values(cx, cz, chunk, heightmap_key)
        result = [None] * 256
        for col, raw_height in enumerate(heights):
            if raw_height <= 0:
                continue
            lx = col & 15
            lz = col >> 4
            y = int(raw_height) + min_y - 1
            name, _props = self.block((cx << 4) + lx, y, (cz << 4) + lz)
            if name not in self._AIR_BLOCKS:
                result[col] = (name, y)
        return result

    def heightmap_surface_block(self, x, z):
        """Return the WORLD_SURFACE block for one column, or None for empty air."""
        cx, cz = x >> 4, z >> 4
        chunk = self.load_chunk(cx, cz)
        if chunk is None:
            return None

        lx, lz = x & 15, z & 15
        heightmap_key = self._surface_heightmap_key(chunk)
        if heightmap_key is None:
            return None
        raw_height = int(self._heightmap_values(cx, cz, chunk, heightmap_key)[lz * 16 + lx])
        if raw_height <= 0:
            return None
        y = raw_height + self._chunk_min_y(chunk) - 1
        name, props = self.block(x, y, z)
        if name in self._AIR_BLOCKS:
            return None
        return name, y, props

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
