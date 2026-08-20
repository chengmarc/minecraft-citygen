"""Top-down world preview rendering helpers."""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np

from config.path_discovery import resolve_region_dir
from engine.anvil_world_reader import World
from engine.render_palette import block_color


# Fill for columns with no generated blocks (ungenerated/empty chunks).
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


def render_topdown_preview(save_path, *, max_size=2048):
    """Render a true top-down surface map from the WORLD_SURFACE heightmaps.

    Renders one pixel per block (block-by-block) for worlds up to ``max_size``
    across; larger worlds are point-sampled so the image stays bounded. Colours
    come from each column's highest non-air block. Region bounds are region-file
    aligned (multiples of 512), so chunks always tile the image edge-to-edge.
    """
    from PIL import Image

    region_dir = resolve_region_dir(save_path)
    world = World(region_dir=region_dir, save_path=save_path)
    x0, x1, z0, z1 = region_world_bounds(region_dir)
    span_x = x1 - x0 + 1
    span_z = z1 - z0 + 1
    step = max(1, math.ceil(max(span_x, span_z) / max_size))

    if step == 1:
        image_array = _render_full_resolution(world, x0, x1, z0, z1, span_x, span_z)
    else:
        image_array = _render_downsampled(world, x0, x1, z0, z1, step)

    image = Image.fromarray(image_array, "RGB")
    return image, {"x0": x0, "x1": x1, "z0": z0, "z1": z1, "step": step}


def _chunk_tile(world, cx, cz, heights):
    """Vectorized 16x16 RGB tile for a chunk from its surface heights, or None."""
    hy = np.array([-1 if v is None else v for v in heights], dtype=np.int64)
    filled = hy >= 0
    if not filled.any():
        return None

    tile = np.empty((256, 3), dtype=np.uint8)
    tile[:] = BACKGROUND
    columns = np.arange(256)
    section_of = np.where(filled, hy >> 4, 0)
    for sy in np.unique(section_of[filled]):
        palette, idx = world._section(cx, cz, int(sy))
        if palette is None:
            continue
        lut = np.array([block_color(str(entry["Name"])) for entry in palette], dtype=np.uint8)
        cols = columns[filled & (section_of == sy)]
        if idx is None:  # uniform section: every block is palette entry 0
            palette_indexes = np.zeros(cols.shape, dtype=np.int64)
        else:
            flat = (hy[cols] & 15) * 256 + cols  # (y&15)*256 + (z&15)*16 + (x&15)
            palette_indexes = np.asarray(idx, dtype=np.int64)[flat]
        tile[cols] = lut[palette_indexes]

    return tile.reshape(16, 16, 3)


def _render_full_resolution(world, x0, x1, z0, z1, span_x, span_z):
    """One pixel per block, pasting a vectorized tile for each chunk."""
    image = np.empty((span_z, span_x, 3), dtype=np.uint8)
    image[:] = BACKGROUND
    for cz in range(z0 >> 4, (z1 >> 4) + 1):
        row = (cz << 4) - z0
        for cx in range(x0 >> 4, (x1 >> 4) + 1):
            heights, _min_y = world.surface_heightmap(cx, cz)
            if heights is None:
                continue
            tile = _chunk_tile(world, cx, cz, heights)
            if tile is not None:
                col = (cx << 4) - x0
                image[row:row + 16, col:col + 16] = tile
    return image


def _render_downsampled(world, x0, x1, z0, z1, step):
    """One heightmap sample per output cell, for worlds larger than the cap."""
    width = math.ceil((x1 - x0 + 1) / step)
    height = math.ceil((z1 - z0 + 1) / step)
    image = np.empty((height, width, 3), dtype=np.uint8)
    image[:] = BACKGROUND
    heightmap_cache = {}
    for iz in range(height):
        wz = min(z1, z0 + iz * step + step // 2)
        for ix in range(width):
            wx = min(x1, x0 + ix * step + step // 2)
            key = (wx >> 4, wz >> 4)
            if key not in heightmap_cache:
                heightmap_cache[key] = world.surface_heightmap(*key)[0]
            heights = heightmap_cache[key]
            if heights is None:
                continue
            y = heights[(wz & 15) * 16 + (wx & 15)]
            if y is not None:
                name, _props = world.block(wx, y, wz)
                image[iz, ix] = block_color(name)
    return image
