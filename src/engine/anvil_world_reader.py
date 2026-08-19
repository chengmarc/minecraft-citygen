"""Minimal reader for modern Anvil worlds (DataVersion 4790 / MC 26.1.x).

Uses only the region container + the section block_states palette/data, so it
does not depend on anvil-parser's (outdated) block decoder.
"""
import struct, zlib, gzip, io, os
import nbtlib

from config.config_world import REGION_DIR, REGION_DIR_CANDIDATES, ROAD_BOX, SAVE
from engine.isometric_renderer import block_color, is_air

GRASS = block_color("minecraft:grass_block", (110, 170, 90))


class World:
    def __init__(self, region_dir=REGION_DIR, save_path=SAVE):
        self.region_dir = region_dir
        self.save_path = save_path
        self._chunks = {}          # (cx,cz) -> chunk nbt (or None)
        self._sections = {}        # (cx,cz,sy) -> (palette, decoded index array or None)
        if not os.path.isdir(self.region_dir):
            checked = REGION_DIR_CANDIDATES or ((self.region_dir,) if self.region_dir else ())
            checked_paths = "\n".join(f"- {path}" for path in checked) or "- <save>/region"
            raise FileNotFoundError(
                "Minecraft world region directory not found.\n"
                f"Configured save: {self.save_path or '<not set>'}\n"
                "Checked:\n"
                f"{checked_paths}\n"
                "Set MC_CITY_SAVE to your world folder or paste it into the Extraction tab."
            )

    def _region_path(self, cx, cz):
        return f"{self.region_dir}/r.{cx >> 5}.{cz >> 5}.mca"

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
                    dec = {1: gzip.decompress, 2: zlib.decompress, 3: lambda b: b}[comp](raw)
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
                        longs = [int(v) & 0xFFFFFFFFFFFFFFFF for v in data]
                        bits = max(4, (len(palette) - 1).bit_length())
                        per = 64 // bits
                        mask = (1 << bits) - 1
                        idx = [0] * 4096
                        for i in range(4096):
                            li, off = divmod(i, per)
                            idx[i] = (longs[li] >> (off * bits)) & mask
                        result = (palette, idx)
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
        props = entry.get("Properties")
        return (str(entry["Name"]), {str(k): str(props[k]) for k in props} if props else None)


# ------------------------------------------------------------------ top-down render
def topdown(x0, x1, z0, z1, y0, y1, scale=8, out="mc_box.png"):
    from PIL import Image
    w = World()
    W, L = x1 - x0 + 1, z1 - z0 + 1
    img = Image.new("RGB", (W * scale, L * scale), GRASS)
    px = img.load()
    seen = {}
    for iz, z in enumerate(range(z0, z1 + 1)):
        for ix, x in enumerate(range(x0, x1 + 1)):
            col = GRASS
            for y in range(y1, y0 - 1, -1):
                name, _ = w.block(x, y, z)
                if is_air(name):
                    continue
                seen[name] = seen.get(name, 0) + 1
                col = block_color(name)
                break
            for dx in range(scale):
                for dy in range(scale):
                    px[ix * scale + dx, iz * scale + dy] = col
    img.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), out))
    print("saved", out, img.size)
    print("surface blocks seen:", dict(sorted(seen.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    topdown(*ROAD_BOX.as_tuple(), scale=8)
