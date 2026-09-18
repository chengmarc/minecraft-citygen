"""Runtime paths: app/resource roots, artifact locations, and world-save region lookup."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from config.env import env_raw

APP_NAME = "Minecraft CityGen"
SOURCE_ROOT = str(Path(__file__).resolve().parents[1])
_REQUIRED_PACKAGE_DIRS = ("config", "engine", "gui", "pipeline")
_REPO_MARKERS = (".git", "application.pyw", "pyproject.toml")


def _norm(path: os.PathLike[str] | str) -> str:
    return os.path.normpath(str(path))


def _resource_root() -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return _norm(base)
    return _norm(SOURCE_ROOT)


def _repo_checkout_root(path: str) -> str:
    package_root = Path(path).resolve()
    if not all((package_root / name).is_dir() for name in _REQUIRED_PACKAGE_DIRS):
        return ""
    if any((package_root / marker).exists() for marker in _REPO_MARKERS):
        return _norm(package_root)
    parent = package_root.parent
    if any((parent / marker).exists() for marker in _REPO_MARKERS):
        return _norm(parent)
    return ""


def _user_data_root() -> str:
    """Per-user writable data dir, following each platform's convention."""
    override = env_raw("APP_ROOT")
    if override:
        return _norm(override)
    home = Path.home()
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(home / "AppData" / "Roaming")
        return _norm(Path(base) / APP_NAME)
    if sys.platform == "darwin":
        return _norm(home / "Library" / "Application Support" / APP_NAME)
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data_home) if xdg_data_home else home / ".local" / "share"
    return _norm(base / APP_NAME)


def _frozen_app_root() -> str:
    exe_root = Path(sys.executable).resolve().parent
    if os.access(exe_root, os.W_OK):
        return _norm(exe_root)
    return _user_data_root()


def _app_root() -> str:
    if getattr(sys, "frozen", False):
        return _frozen_app_root()
    repo_root = _repo_checkout_root(SOURCE_ROOT)
    if repo_root:
        return repo_root
    return _user_data_root()


RESOURCE_ROOT = _resource_root()
ROOT = _app_root()
CONFIG = str(Path(RESOURCE_ROOT) / "config")
GUI = str(Path(RESOURCE_ROOT) / "gui")
GUI_ICONS = str(Path(GUI) / "icons")
APP_ICON = str(Path(GUI_ICONS) / "app-icon.png")  # window icon and exported worlds' save-list icon
DEFAULT_WORLD = str(Path(RESOURCE_ROOT) / "config" / "default_world")
ARTIFACTS = str(Path(ROOT) / "artifacts")


def _artifact_dir(*parts: str) -> str:
    return str(Path(ARTIFACTS).joinpath(*parts))


CONTACT_SHEET = "_contact_sheet.png"  # every asset folder's labelled thumbnail grid

ROADS_SCHEM = _artifact_dir("01_roads", "schem")
ROADS_RENDERS = _artifact_dir("01_roads", "renders")
ROADS_CONTACT_SHEET = str(Path(ROADS_RENDERS) / CONTACT_SHEET)

BUILDS_SCHEM = _artifact_dir("02_builds", "schem")
BUILDS_RENDERS = _artifact_dir("02_builds", "renders")
BUILDS_CONTACT_SHEET = str(Path(BUILDS_RENDERS) / CONTACT_SHEET)
BUILD_CATALOG = _artifact_dir("02_builds", "buildings.json")
BUILDS_GIF = _artifact_dir("02_builds", "buildings.gif")

PREVIEW_ROADS = _artifact_dir("03_preview", "roads")
PREVIEW_ROADS_CONTACT_SHEET = str(Path(PREVIEW_ROADS) / CONTACT_SHEET)
PREVIEW_BUILDS = _artifact_dir("03_preview", "builds")
PREVIEW_BUILDS_CONTACT_SHEET = str(Path(PREVIEW_BUILDS) / CONTACT_SHEET)
PREVIEW_GRID = _artifact_dir("03_preview", "grid")
PREVIEW_CITY = _artifact_dir("03_preview", "city")

CITY_SCHEM = _artifact_dir("04_city", "schem")
CITY_RENDERS = _artifact_dir("04_city", "renders")

# Standalone Minecraft worlds exported from the final city (one folder per seed).
SAVES = _artifact_dir("05_world", "saves")
EXPORTED_WORLD_NAME = f"{APP_NAME} World"

# Cached top-down world renders for the GUI region selector.
WORLD_PREVIEW_CACHE = _artifact_dir("world_preview")

COLOR_RENDER_CSV = str(Path(CONFIG) / "color_render.csv")


# Per-seed artifacts: every stage and the GUI derive these names from here.
def grid_preview_path(seed) -> str:
    return str(Path(PREVIEW_GRID) / f"seed_{seed}.png")


def city_preview_path(seed) -> str:
    return str(Path(PREVIEW_CITY) / f"seed_{seed}.png")


def city_schem_path(seed) -> str:
    return str(Path(CITY_SCHEM) / f"seed_{seed}.schem")


def city_render_path(seed) -> str:
    return str(Path(CITY_RENDERS) / f"seed_{seed}.png")


def exported_world_name(seed) -> str:
    return f"{EXPORTED_WORLD_NAME} {seed}"


def exported_world_path(seed) -> str:
    return str(Path(SAVES) / exported_world_name(seed))


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


def _contains_region_files(region_dir: str) -> bool:
    return bool(region_dir) and os.path.isdir(region_dir) and any(Path(region_dir).glob("r.*.*.mca"))


def has_region_files(save_path: os.PathLike[str] | str | None) -> bool:
    """Return True when save_path contains at least one .mca region file."""
    return _contains_region_files(resolve_region_dir(save_path))


def resolve_region_dir(save_path: os.PathLike[str] | str | None) -> str:
    candidates = region_dir_candidates(save_path)
    for candidate in candidates:
        if _contains_region_files(candidate):
            return candidate
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return candidates[0] if candidates else ""
