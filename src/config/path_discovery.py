"""Filesystem path helpers for Minecraft world saves."""

from __future__ import annotations

import os
from pathlib import Path


def _normalized(path: os.PathLike[str] | str | None) -> str:
    if not path:
        return ""
    return os.path.normpath(str(Path(path).expanduser()))


def region_dir_candidates(save_path: os.PathLike[str] | str | None) -> list[str]:
    save_root = _normalized(save_path)
    if not save_root:
        return []
    base = Path(save_root)
    if base.name.lower() == "region":
        return [str(base)]
    return [
        os.path.normpath(str(base / "region")),
        os.path.normpath(str(base / "dimensions" / "minecraft" / "overworld" / "region")),
    ]


def is_world_save(save_path: os.PathLike[str] | str | None) -> bool:
    return any(os.path.isdir(candidate) for candidate in region_dir_candidates(save_path))


def has_region_files(save_path: os.PathLike[str] | str | None) -> bool:
    """Return True when save_path contains at least one .mca region file."""
    region_dir = resolve_region_dir(save_path)
    if not region_dir or not os.path.isdir(region_dir):
        return False
    return any(Path(region_dir).glob("r.*.*.mca"))


def resolve_region_dir(save_path: os.PathLike[str] | str | None) -> str:
    candidates = region_dir_candidates(save_path)
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return candidates[0] if candidates else ""
