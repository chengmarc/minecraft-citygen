"""The region map's picture: the world's top-down preview, rendered once per world and cached on disk.

The only part of the GUI that calls the engine directly: the map is a picture of the source world, not a pipeline
stage, and it's drawn while the user is still choosing what the pipeline will extract.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from config.path import WORLD_PREVIEW_CACHE, resolve_region_dir
from engine.render.topdown import render_topdown_preview


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


def cached_topdown_preview(save_path, on_progress=None, on_partial=None):
    """The world's top-down preview as ``(png_path, meta)``, rendered only when the cache is stale.

    The cache in ``WORLD_PREVIEW_CACHE`` is keyed on save_path and invalidated when
    any .mca file changes, so reopening the region map is instant. ``on_progress``
    and ``on_partial(png_path, meta)`` are only called on a cache miss (an actual
    render): each picture so far is saved beside the cache as its own
    ``<key>.partial-<n>.png``, so a page still fetching one gets that picture and not
    a later one. A render clears the last render's; every launch clears them all.
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
