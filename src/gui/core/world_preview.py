"""The world's top-down preview for the region map, rendered once per world and cached on disk."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from config.path import WORLD_PREVIEW_CACHE, resolve_region_dir
from engine.render.topdown import render_topdown_preview

CHUNK_SIZE = 16


def _preview_cache_paths(save_path):
    key = hashlib.md5(str(save_path).encode()).hexdigest()[:16]
    cache_dir = Path(WORLD_PREVIEW_CACHE)
    return cache_dir / f"{key}.png", cache_dir / f"{key}.json"


def _preview_region_mtime(save_path):
    try:
        region_dir = resolve_region_dir(save_path)
        mtimes = [p.stat().st_mtime for p in Path(region_dir).glob("*.mca")]
        return max(mtimes) if mtimes else 0.0
    except Exception:
        return 0.0


def cached_topdown_preview(save_path, on_progress=None):
    """The world's top-down preview as ``(png_path, meta)``, rendered only when the cache is stale.

    The cache in ``WORLD_PREVIEW_CACHE`` is keyed on save_path and invalidated when
    any .mca file changes, so reopening the region map is instant. ``on_progress``
    is only called on a cache miss (an actual render).
    """
    png_path, json_path = _preview_cache_paths(save_path)
    mtime = _preview_region_mtime(save_path)

    if png_path.exists() and json_path.exists():
        try:
            with open(json_path) as f:
                cached_meta = json.load(f)
            if cached_meta.get("mtime") == mtime:
                return png_path, {k: v for k, v in cached_meta.items() if k != "mtime"}
        except Exception:
            pass  # fall through to re-render on any cache read failure

    image, meta = render_topdown_preview(save_path, on_progress=on_progress)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(png_path)
    with open(json_path, "w") as f:
        json.dump({**meta, "mtime": mtime}, f)
    return png_path, meta


def chunk_span_text(start, end):
    """How many chunks a block region covers, as "x x z chunks"."""
    min_x, max_x = sorted((int(start[0]), int(end[0])))
    min_z, max_z = sorted((int(start[2]), int(end[2])))
    x_chunks = max_x // CHUNK_SIZE - min_x // CHUNK_SIZE + 1
    z_chunks = max_z // CHUNK_SIZE - min_z // CHUNK_SIZE + 1
    return f"{x_chunks} x {z_chunks} chunks"
