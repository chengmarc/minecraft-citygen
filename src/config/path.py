"""Config primitives: environment overrides and runtime path helpers.

Three base-layer concerns live here so the rest of :mod:`config` builds on one
module:

* ``env_*`` -- typed readers for ``MC_CITY_*`` overrides. Every tunable in
  :mod:`config` can be overridden by ``MC_CITY_<NAME>``; these helpers apply the
  same contract (unset or blank falls back to the default) and hold no state, so
  the in-process reload mechanism (see :mod:`pipeline.runtime`) picks up
  overrides simply by re-importing the config module that calls them.
* path constants for source, installed, and frozen CityGen runtimes. Path
  building uses ``pathlib``; the public constants are exported as normalized
  ``str`` values because the rest of the codebase joins onto them with
  ``os.path.join``. ``os`` is used only for ``os.environ``, ``os.access``, and
  ``os.path.normpath`` (pure normalization, which has no ``pathlib`` equivalent).
* world-save discovery helpers that locate a save's region directory.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ------------------------------------------------------------- env overrides
PREFIX = "MC_CITY_"


def env_raw(name: str) -> str | None:
    """Raw value of ``MC_CITY_<name>``, or ``None`` when unset or blank."""
    value = os.environ.get(f"{PREFIX}{name}")
    if value is None or not value.strip():
        return None
    return value


def env_str(name: str, default: str) -> str:
    """String override, falling back to ``default`` when unset or blank."""
    value = env_raw(name)
    return default if value is None else value


def env_int(name: str, default: int) -> int:
    """Integer override, falling back to ``default`` when unset or blank."""
    value = env_raw(name)
    return default if value is None else int(value.strip())


def env_set(name: str, default) -> set[str]:
    """Comma/semicolon-separated string set, falling back to ``default``.

    ``default`` is copied into a fresh set so callers can pass a literal without
    it being shared across reloads.
    """
    value = env_raw(name)
    if value is None:
        return set(default)
    return {part.strip() for part in value.replace(";", ",").split(",") if part.strip()}


# ------------------------------------------------------------ path constants
APP_NAME = "CityGen"
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


def _frozen_app_root(executable: str | None = None) -> str:
    executable = executable or sys.executable
    exe_root = Path(executable).resolve().parent
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
DEFAULT_WORLD = str(Path(RESOURCE_ROOT) / "config" / "default_world")
ARTIFACTS = str(Path(ROOT) / "artifacts")


def _artifact_dir(*parts: str) -> str:
    return str(Path(ARTIFACTS).joinpath(*parts))


ROADS_SIM = _artifact_dir("roads", "simulation")
ROADS_PROD = _artifact_dir("roads", "production")

GRID_SIM = _artifact_dir("grid", "simulation")
GRID_PROD = _artifact_dir("grid", "production")

BUILDS_SIM = _artifact_dir("builds", "simulation")
BUILDS_PROD = _artifact_dir("builds", "production")
BUILD_CATALOG = str(Path(BUILDS_PROD) / "buildings.json")

CITY_SIM = _artifact_dir("city", "simulation")
CITY_PROD = _artifact_dir("city", "production")

# Standalone Minecraft worlds exported from the final city (one folder per seed).
SAVES = _artifact_dir("saves")

COLOR_RENDER_CSV = str(Path(CONFIG) / "color_render.csv")


# --------------------------------------------------------- world-save lookup
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
