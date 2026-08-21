"""Path constants for source, installed, and frozen CityGen runtimes.

Path building uses ``pathlib`` throughout; the public constants are exported as
normalized ``str`` values because the rest of the codebase joins onto them with
``os.path.join``. ``os`` is used only for ``os.environ``, ``os.access``, and
``os.path.normpath`` (pure normalization, which has no ``pathlib`` equivalent).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "CityGen"
SOURCE_ROOT = str(Path(__file__).resolve().parents[1])
_REQUIRED_PACKAGE_DIRS = ("config", "engine", "gui", "pipeline")
_REPO_MARKERS = (".git", "application.pyw", "docs/TECHNICAL.md")


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
    override = os.environ.get("MC_CITY_APP_ROOT")
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
ENGINE = str(Path(RESOURCE_ROOT) / "engine")
PIPELINE = str(Path(RESOURCE_ROOT) / "pipeline")
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

COLOR_RENDER_CSV = str(Path(CONFIG) / "color_render.csv")
