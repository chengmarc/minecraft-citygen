"""Top-down world preview rendering helpers."""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np

from config.path import resolve_region_dir
from engine.world.anvil_world_reader import World
from engine.render.palette import block_color

BACKGROUND = (36, 40, 48)
REGION_FILE_PATTERN = re.compile(r"^r\.(-?\d+)\.(-?\d+)\.mca$")


def _region_coords(region_dir):
    for path in Path(region_dir).glob("r.*.*.mca"):
        match = REGION_FILE_PATTERN.match(path.name)
        if match is not None:
            yield int(match.group(1)), int(match.group(2))


def region_world_bounds(region_dir):
    coords = list(_region_coords(region_dir))
    if not coords:
        raise FileNotFoundError(f"No Minecraft region files were found in {region_dir}")
    min_rx = min(rx for rx, _rz in coords)
    max_rx = max(rx for rx, _rz in coords)
    min_rz = min(rz for _rx, rz in coords)
    max_rz = max(rz for _rx, rz in coords)
    return (
        min_rx * 512,
        (max_rx + 1) * 512 - 1,
        min_rz * 512,
        (max_rz + 1) * 512 - 1,
    )


def render_topdown_preview(save_path, *, max_size=2048, on_progress=None):
    from PIL import Image

    region_dir = resolve_region_dir(save_path)
    world = World(region_dir=region_dir, save_path=save_path)
    x0, x1, z0, z1 = region_world_bounds(region_dir)
    span_x = x1 - x0 + 1
    span_z = z1 - z0 + 1
    step = max(1, math.ceil(max(span_x, span_z) / max_size))

    width = math.ceil(span_x / step)
    height = math.ceil(span_z / step)
    image = np.full((height, width, 3), BACKGROUND, dtype=np.uint8)

    if step == 1:
        cz_range = range(z0 >> 4, (z1 >> 4) + 1)
        cx_range = range(x0 >> 4, (x1 >> 4) + 1)
        total = len(cz_range)
        for i, cz in enumerate(cz_range):
            for cx in cx_range:
                if world.is_chunk_empty(cx, cz):
                    continue
                entries = world.top_solid_blocks(cx, cz)
                tile = np.array(
                    [block_color(e[0]) if e is not None else BACKGROUND for e in entries],
                    dtype=np.uint8,
                ).reshape(16, 16, 3)
                image[(cz << 4) - z0:(cz << 4) - z0 + 16,
                      (cx << 4) - x0:(cx << 4) - x0 + 16] = tile
            if on_progress is not None:
                on_progress(i + 1, total)
    else:
        empty_chunks = set()
        for iz in range(height):
            wz = min(z1, z0 + iz * step)
            for ix in range(width):
                wx = min(x1, x0 + ix * step)
                key = (wx >> 4, wz >> 4)
                if key in empty_chunks:
                    continue
                if world.is_chunk_empty(*key):
                    empty_chunks.add(key)
                    continue
                result = world.top_solid_block(wx, wz)
                if result is not None:
                    image[iz, ix] = block_color(result[0])
            if on_progress is not None:
                on_progress(iz + 1, height)

    return Image.fromarray(image, "RGB"), {"x0": x0, "x1": x1, "z0": z0, "z1": z1, "step": step}
