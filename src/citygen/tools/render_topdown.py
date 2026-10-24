"""The region map's picture: the source world drawn from above, cached on disk once per world.

It's drawn while the user is still choosing the areas to extract, so it isn't part of any tab's run.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from pathlib import Path

import numpy as np

from citygen.tools.blocks import block_color
from citygen.tools.world_reader import resolve_region_dir, World

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

    world = World(save_path)
    x0, x1, z0, z1 = region_world_bounds(world.region_dir)
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


# --- The cache


def _preview_cache_paths(save_path, cache_dir):
    key = hashlib.md5(str(save_path).encode()).hexdigest()[:16]
    cache_dir = Path(cache_dir)
    return cache_dir / f"{key}.png", cache_dir / f"{key}.json"


def _preview_region_mtime(save_path):
    try:
        region_dir = resolve_region_dir(save_path)
        mtimes = [p.stat().st_mtime for p in Path(region_dir).glob("*.mca")]
        return max(mtimes) if mtimes else 0.0
    except Exception:
        return 0.0


def cached_topdown_preview(save_path, cache_dir, on_progress=None, on_partial=None):
    """The world's top-down preview as ``(png_path, meta)``, rendered only when the cache is stale.

    The cache in ``cache_dir`` is keyed on save_path and invalidated when
    any .mca file changes, so reopening the region map is instant. ``on_progress``
    and ``on_partial(png_path, meta)`` are only called on a cache miss (an actual
    render): each picture so far is saved beside the cache as its own
    ``<key>.partial-<n>.png``, so a page still fetching one gets that picture and not
    a later one. A render clears the last render's; every launch clears them all.
    """
    png_path, json_path = _preview_cache_paths(save_path, cache_dir)
    mtime = _preview_region_mtime(save_path)

    if png_path.exists() and json_path.exists():
        try:
            with open(json_path) as f:
                cached_meta = json.load(f)
            if cached_meta.get("mtime") == mtime:
                return png_path, {k: v for k, v in cached_meta.items() if k != "mtime"}
        except Exception:
            pass  # fall through to re-render on any cache read failure

    png_path.parent.mkdir(parents=True, exist_ok=True)
    for old in png_path.parent.glob(f"{png_path.stem}.partial-*.png"):
        old.unlink(missing_ok=True)
    partials = 0

    def save_partial(image, meta):
        nonlocal partials
        partials += 1
        path = png_path.with_name(f"{png_path.stem}.partial-{partials}.png")
        image.save(path)
        on_partial(path, meta)

    image, meta = render_topdown_preview(
        save_path, on_progress=on_progress, on_partial=save_partial if on_partial is not None else None,
    )
    image.save(png_path)
    with open(json_path, "w") as f:
        json.dump({**meta, "mtime": mtime}, f)
    return png_path, meta
