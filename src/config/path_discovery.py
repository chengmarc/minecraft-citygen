"""Filesystem path discovery helpers for portable CityGen defaults."""

from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _normalized(path: os.PathLike[str] | str | None) -> str:
    if not path:
        return ""
    return os.path.normpath(str(Path(path).expanduser()))


def _unique(paths: list[os.PathLike[str] | str | None]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for path in paths:
        normalized = _normalized(path)
        if not normalized:
            continue
        folded = os.path.normcase(normalized)
        if folded in seen:
            continue
        seen.add(folded)
        ordered.append(normalized)
    return ordered


def region_dir_candidates(save_path: os.PathLike[str] | str | None) -> list[str]:
    save_root = _normalized(save_path)
    if not save_root:
        return []
    base = Path(save_root)
    if base.name.lower() == "region":
        return [str(base)]
    return _unique(
        [
            base / "region",
            base / "dimensions" / "minecraft" / "overworld" / "region",
        ]
    )


def resolve_region_dir(save_path: os.PathLike[str] | str | None) -> str:
    candidates = region_dir_candidates(save_path)
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return candidates[0] if candidates else ""


def _appdata_root() -> Path:
    return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")).expanduser()


def _iter_instance_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    try:
        return sorted(path for path in root.iterdir() if path.is_dir())
    except OSError:
        return []


def candidate_save_roots() -> list[str]:
    appdata = _appdata_root()
    candidates: list[Path] = [appdata / ".minecraft" / "saves"]

    for launcher in ("PrismLauncher", "MultiMC", "PolyMC"):
        for instance in _iter_instance_dirs(appdata / launcher / "instances"):
            candidates.append(instance / "minecraft" / "saves")

    for instance in _iter_instance_dirs(appdata / "CurseForge" / "Minecraft" / "Instances"):
        candidates.append(instance / ".minecraft" / "saves")

    return _unique(path for path in candidates if path.is_dir())


def discover_default_save() -> str:
    discovered: list[Path] = []
    for root in candidate_save_roots():
        try:
            children = sorted(path for path in Path(root).iterdir() if path.is_dir())
        except OSError:
            continue
        for child in children:
            if any(os.path.isdir(candidate) for candidate in region_dir_candidates(child)):
                discovered.append(child)
    if not discovered:
        return ""
    return str(max(discovered, key=lambda path: path.stat().st_mtime if path.exists() else 0))


def worldedit_dir_candidates(save_path: os.PathLike[str] | str | None = None) -> list[str]:
    appdata = _appdata_root()
    candidates: list[Path | str] = []

    explicit = os.environ.get("MC_CITY_WORLDEDIT_SCHEM")
    if explicit:
        candidates.append(explicit)

    save_root = _normalized(save_path)
    if save_root:
        base = Path(save_root)
        for parent in (base, *base.parents):
            if parent.name.lower() == "minecraft":
                candidates.append(parent / "config" / "worldedit" / "schematics")
                break

    candidates.append(appdata / ".minecraft" / "config" / "worldedit" / "schematics")

    for launcher in ("PrismLauncher", "MultiMC", "PolyMC"):
        for instance in _iter_instance_dirs(appdata / launcher / "instances"):
            candidates.append(instance / "minecraft" / "config" / "worldedit" / "schematics")

    for instance in _iter_instance_dirs(appdata / "CurseForge" / "Minecraft" / "Instances"):
        candidates.append(instance / ".minecraft" / "config" / "worldedit" / "schematics")

    return _unique(candidates)


def discover_worldedit_schematics(
    save_path: os.PathLike[str] | str | None = None,
    fallback_dir: os.PathLike[str] | str | None = None,
) -> str:
    for candidate in worldedit_dir_candidates(save_path):
        if os.path.isdir(candidate):
            return candidate
    fallback = fallback_dir or (REPO_ROOT / "artifacts" / "worldedit")
    return _normalized(fallback)
