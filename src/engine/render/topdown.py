"""Top-down world preview rendering helpers."""

from __future__ import annotations

import math
import re
import time
from pathlib import Path

import numpy as np

from config.path import resolve_region_dir
from engine.world.anvil_world_reader import World
from engine.render.palette import block_color

# Where there's no world (no chunk, or no surface block), the map is transparent: it shows whatever it's drawn on.
EMPTY = (0, 0, 0, 0)
MAX_PREVIEW_SIZE = 2048
PARTIAL_EVERY_SECONDS = 0.4
REGION_FILE_PATTERN = re.compile(r"^r\.(-?\d+)\.(-?\d+)\.mca$")


def _region_coords(region_dir):
    for path in Path(region_dir).glob("r.*.*.mca"):
        match = REGION_FILE_PATTERN.match(path.name)
        if match is not None:
            yield int(match.group(1)), int(match.group(2))


def region_world_bounds(region_dir):
    coords = list(_region_coords(region_dir))
    if not coords:
        raise FileNotFoundError(f"No MC region files were found in {region_dir}")
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


def render_topdown_preview(save_path, *, on_progress=None, on_partial=None):
    """The world from above as ``(image, meta)``; ``meta`` maps its pixels to blocks (x0..x1, z0..z1, ``step`` blocks
    a pixel).

    It's drawn row by row, from the top: ``on_progress(done, total)`` after each row, and ``on_partial(image, meta)``
    with the picture so far, at most every ``PARTIAL_EVERY_SECONDS``, for showing it as it's drawn.
    """
    from PIL import Image

    region_dir = resolve_region_dir(save_path)
    world = World(region_dir=region_dir, save_path=save_path)
    x0, x1, z0, z1 = region_world_bounds(region_dir)
    span_x = x1 - x0 + 1
    span_z = z1 - z0 + 1
    step = max(1, math.ceil(max(span_x, span_z) / MAX_PREVIEW_SIZE))

    width = math.ceil(span_x / step)
    height = math.ceil(span_z / step)
    image = np.zeros((height, width, 4), dtype=np.uint8)   # all EMPTY until drawn
    meta = {"x0": x0, "x1": x1, "z0": z0, "z1": z1, "step": step}
    last_partial = time.monotonic()

    def row_done(done, total):
        nonlocal last_partial
        if on_progress is not None:
            on_progress(done, total)
        if on_partial is not None and done < total and time.monotonic() - last_partial >= PARTIAL_EVERY_SECONDS:
            last_partial = time.monotonic()
            on_partial(Image.fromarray(image, "RGBA"), meta)

    if step == 1:
        cz_range = range(z0 >> 4, (z1 >> 4) + 1)
        cx_range = range(x0 >> 4, (x1 >> 4) + 1)
        total = len(cz_range)
        for i, cz in enumerate(cz_range):
            for cx in cx_range:
                if world.is_chunk_empty(cx, cz):
                    continue
                entries = world.heightmap_surface_blocks(cx, cz)
                tile = np.array(
                    [(*block_color(e[0]), 255) if e is not None else EMPTY for e in entries],
                    dtype=np.uint8,
                ).reshape(16, 16, 4)
                image[(cz << 4) - z0:(cz << 4) - z0 + 16,
                      (cx << 4) - x0:(cx << 4) - x0 + 16] = tile
            row_done(i + 1, total)
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
                result = world.heightmap_surface_block(wx, wz)
                if result is not None:
                    image[iz, ix] = (*block_color(result[0]), 255)
            row_done(iz + 1, height)

    return Image.fromarray(image, "RGBA"), meta
