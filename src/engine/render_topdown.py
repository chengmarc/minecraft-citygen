"""Top-down world preview rendering helpers."""

from __future__ import annotations

import math
import re
from pathlib import Path

from config.path_discovery import resolve_region_dir
from engine.anvil_world_reader import World
from engine.render_palette import block_color, is_air


GRASS = block_color("minecraft:grass_block", (110, 170, 90))
REGION_FILE_PATTERN = re.compile(r"^r\.(-?\d+)\.(-?\d+)\.mca$")


def region_world_bounds(region_dir):
    coords = []
    for path in Path(region_dir).glob("r.*.*.mca"):
        match = REGION_FILE_PATTERN.match(path.name)
        if match is not None:
            coords.append((int(match.group(1)), int(match.group(2))))
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


def render_topdown_preview(save_path, y0, y1, *, max_size=768):
    from PIL import Image

    region_dir = resolve_region_dir(save_path)
    world = World(region_dir=region_dir, save_path=save_path)
    x0, x1, z0, z1 = region_world_bounds(region_dir)
    span_x = x1 - x0 + 1
    span_z = z1 - z0 + 1
    step = max(1, math.ceil(max(span_x, span_z) / max_size))
    width = math.ceil(span_x / step)
    height = math.ceil(span_z / step)
    ylo, yhi = sorted((int(y0), int(y1)))

    image = Image.new("RGB", (width, height), GRASS)
    pixels = image.load()
    for iz in range(height):
        sample_z = min(z1, z0 + iz * step + step // 2)
        for ix in range(width):
            sample_x = min(x1, x0 + ix * step + step // 2)
            color = GRASS
            for y in range(yhi, ylo - 1, -1):
                name, _props = world.block(sample_x, y, sample_z)
                if is_air(name):
                    continue
                color = block_color(name)
                break
            pixels[ix, iz] = color

    return image, {
        "x0": x0,
        "x1": x1,
        "z0": z0,
        "z1": z1,
        "step": step,
    }
