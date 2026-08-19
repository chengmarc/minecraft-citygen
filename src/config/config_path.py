"""Path constants for source, installed, and frozen CityGen runtimes."""

from __future__ import annotations

import os
import sys

from config.path_discovery import discover_worldedit_schematics


APP_NAME = "CityGen"
SOURCE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(SOURCE_ROOT)
APPDATA = os.environ.get("APPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Roaming"))


def _resource_root() -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.normpath(base)
    return SOURCE_ROOT


def _repo_checkout_root(path: str) -> str:
    required_dirs = ("config", "engine", "gui", "pipeline")
    if not all(os.path.isdir(os.path.join(path, name)) for name in required_dirs):
        return ""
    markers = (".git", "application.pyw", os.path.join("docs", "TECHNICAL.md"))
    if any(os.path.exists(os.path.join(path, marker)) for marker in markers):
        return os.path.normpath(path)
    parent = os.path.dirname(path)
    if any(os.path.exists(os.path.join(parent, marker)) for marker in markers):
        return os.path.normpath(parent)
    return ""


def _is_repo_checkout(path: str) -> bool:
    return bool(_repo_checkout_root(path))


def _user_data_root() -> str:
    override = os.environ.get("MC_CITY_APP_ROOT")
    if override:
        return os.path.normpath(override)
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return os.path.normpath(os.path.join(local_appdata, APP_NAME))
    return os.path.normpath(os.path.join(APPDATA, APP_NAME))


def _frozen_app_root(executable: str | None = None) -> str:
    executable = executable or sys.executable
    exe_root = os.path.dirname(os.path.abspath(executable))
    if os.access(exe_root, os.W_OK):
        return os.path.normpath(exe_root)
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

WORLDEDIT_SCHEM = discover_worldedit_schematics(
    os.environ.get("MC_CITY_SAVE"),
    _artifact_dir("worldedit"),
)

COLOR_RENDER_CSV = os.path.join(ENGINE, "color_render.csv")
