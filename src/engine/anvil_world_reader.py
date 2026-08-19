"""Minimal reader for modern Anvil worlds (DataVersion 4790 / MC 26.1.x).

Uses only the region container + the section block_states palette/data, so it
does not depend on anvil-parser's (outdated) block decoder.
"""
from __future__ import annotations

import gzip
import io
import os
import struct
import zlib

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
        if not os.path.isdir(self.region_dir):
            checked = _checked_region_paths(self.region_dir, self.save_path, REGION_DIR_CANDIDATES)
            raise FileNotFoundError(_missing_region_dir_message(self.save_path, checked))

    def _region_path(self, cx, cz):
        return f"{self.region_dir}/r.{cx >> 5}.{cz >> 5}.mca"

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
        longs = [int(value) & 0xFFFFFFFFFFFFFFFF for value in data]
        bits = max(4, (palette_size - 1).bit_length())
        per_long = 64 // bits
        mask = (1 << bits) - 1
        indexes = [0] * 4096
        for i in range(4096):
            long_index, offset = divmod(i, per_long)
            indexes[i] = (longs[long_index] >> (offset * bits)) & mask
        return indexes

    @staticmethod
    def _block_properties(entry):
        props = entry.get("Properties")
        return {str(key): str(props[key]) for key in props} if props else None

    def _load_chunk(self, cx, cz):
        if (cx, cz) in self._chunks:
            return self._chunks[(cx, cz)]
        path = self._region_path(cx, cz)
        chunk = None
        if os.path.exists(path):
            with open(path, "rb") as f:
                header = f.read(4096)
                loc = (cx & 31) + (cz & 31) * 32
                entry = struct.unpack_from(">I", header, loc * 4)[0]
                offset = entry >> 8
                if offset:
                    f.seek(offset * 4096)
                    length = struct.unpack(">I", f.read(4))[0]
                    comp = f.read(1)[0]
                    raw = f.read(length - 1)
                    dec = self._decode_chunk_payload(raw, comp)
                    chunk = nbtlib.File.parse(io.BytesIO(dec))
        self._chunks[(cx, cz)] = chunk
        return chunk

    def _section(self, cx, cz, sy):
        key = (cx, cz, sy)
        if key in self._sections:
            return self._sections[key]
        chunk = self._load_chunk(cx, cz)
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

    def block(self, x, y, z):
        """Return (name, properties_dict_or_None) or ('minecraft:air', None)."""
        cx, cz, sy = x >> 4, z >> 4, y >> 4
        palette, idx = self._section(cx, cz, sy)
        if palette is None:
            return ("minecraft:air", None)
        v = 0 if idx is None else idx[(y & 15) * 256 + (z & 15) * 16 + (x & 15)]
        entry = palette[v]
        return str(entry["Name"]), self._block_properties(entry)
