"""Path constants for source, installed, and frozen CityGen runtimes."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "CityGen"
SOURCE_ROOT = str(Path(__file__).resolve().parents[1])
APPDATA = os.environ.get("APPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Roaming"))
_REQUIRED_PACKAGE_DIRS = ("config", "engine", "gui", "pipeline")
_REPO_MARKERS = (".git", "application.pyw", os.path.join("docs", "TECHNICAL.md"))


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
    override = os.environ.get("MC_CITY_APP_ROOT")
    if override:
        return _norm(override)
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return _norm(Path(local_appdata) / APP_NAME)
    return _norm(Path(APPDATA) / APP_NAME)


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
ENGINE = os.path.join(RESOURCE_ROOT, "engine")
PIPELINE = os.path.join(RESOURCE_ROOT, "pipeline")
GUI = os.path.join(RESOURCE_ROOT, "gui")
DEFAULT_WORLD = os.path.join(RESOURCE_ROOT, "config", "default_world")
ARTIFACTS = os.path.join(ROOT, "artifacts")


def _artifact_dir(*parts):
    return os.path.join(ARTIFACTS, *parts)


ROADS_SIM = _artifact_dir("roads", "simulation")
ROADS_PROD = _artifact_dir("roads", "production")
ROADS_PROD_SCHEM = ROADS_PROD

GRID_SIM = _artifact_dir("grid", "simulation")
GRID_PROD = _artifact_dir("grid", "production")
GRID_PROD_SCHEM = GRID_PROD

BUILDS_SIM = _artifact_dir("builds", "simulation")
BUILDS_PROD = _artifact_dir("builds", "production")
BUILDS_PROD_SCHEM = BUILDS_PROD
BUILD_CATALOG = os.path.join(BUILDS_PROD, "buildings.json")

CITY_SIM = _artifact_dir("city", "simulation")
CITY_PROD = _artifact_dir("city", "production")
CITY_PROD_SCHEM = CITY_PROD

WORLDEDIT_SCHEM = os.path.normpath(
    os.environ.get("MC_CITY_WORLDEDIT_SCHEM") or _artifact_dir("worldedit")
)

COLOR_RENDER_CSV = os.path.join(ENGINE, "color_render.csv")
