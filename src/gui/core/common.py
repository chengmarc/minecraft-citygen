"""Shared Qt-era GUI constants and non-widget helpers."""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys

from config import algo
from config.algo import DEFAULT_SEED
from config.path import (
    ARTIFACTS, BUILDS_RENDERS, CITY_RENDERS, PREVIEW_CITY,
    PREVIEW_GRID, GUI, ROOT, ROADS_RENDERS, SAVES,
)
from config.world import (
    BUILD_TYPES, HARD_FLOOR_DATA_VERSION, RELEASE_NAMES, ROAD_BOX, SAVE,
    BlockRegion, BuildRegion, detect_world_data_version, release_name_for,
)


class SeedError(ValueError):
    """Raised when the seed field does not hold a valid integer."""


class ConfigError(ValueError):
    """Raised when an algorithm/city config value is invalid."""


ROOT_DIR = ROOT
ICON_DIR = os.path.join(GUI, "icons")
CONFIG_DIR = os.path.join(ROOT_DIR, "src", "config")
APP_ICON_PATH = os.path.join(ICON_DIR, "app-icon.png")
ROAD_CONTACT_SHEET = os.path.join(ROADS_RENDERS, "_contact_sheet.png")
BUILD_CONTACT_SHEET = os.path.join(BUILDS_RENDERS, "_contact_sheet.png")

APP_WIDTH = 1366
APP_HEIGHT = 768
STARTUP_ERROR_LOG = os.path.join(ROOT_DIR, "application_startup_error.log")
PROGRESS_TIMINGS_PATH = os.path.join(ARTIFACTS, "progress_timings.json")
LEGACY_SAVED_GUI_CONFIG_PATH = os.path.join(ROOT_DIR, "citygen_saved_config.json")
SAVED_GUI_CONFIG_PATH = os.path.join(CONFIG_DIR, "citygen.json")

PREVIEW_CONFIGS = [
    ("FINE", "City Size", "Changes the footprint of the finished city."),
    ("GAP_MIXED", "Road Density", "Controls how tightly Avenues and Streets are packed across the city."),
    ("GAP_BIG", "Avenue Spacing", "Higher values create fewer Avenues."),
    ("PAD_BIG", "Avenue Edge Margin", "Keeps Avenues farther from the edge of the city."),
    ("GAP_SMALL", "Street Spacing", "Lower values create more Streets."),
    ("PAD_SMALL", "Street Edge Margin", "Keeps Streets farther from the edge of the city."),
    ("N_BIG_CORNERS", "Avenue Turns", "Adds more bends to Avenues."),
    ("N_BIG_TEES", "Avenue T-Junctions", "Adds more T-junctions to Avenues."),
    ("N_SMALL_CORNERS", "Street Turns", "Adds more bends to Streets."),
    ("N_SMALL_TEES", "Street T-Junctions", "Adds more T-junctions to Streets."),
    ("BANNED_BUILDINGS", "Skip Building IDs", "Optional comma-separated building IDs to leave out of generation."),
    ("TYPE1_TOP_FIT_CHOICES", "House Style Variety", "Higher values mix in more different standard house designs."),
    ("LANDMARK_SPACING", "Landmark Spacing", "Minimum fine-cell distance between landmark footprints."),
]
PREVIEW_CONFIG_LOOKUP = {name: (label, description) for name, label, description in PREVIEW_CONFIGS}

PREVIEW_CONFIG_GROUPS = [
    ("Avenue and Street Spacing", ["GAP_BIG", "PAD_BIG", "GAP_SMALL", "PAD_SMALL"]),
    ("Avenue and Street Shape", ["N_BIG_CORNERS", "N_BIG_TEES", "N_SMALL_CORNERS", "N_SMALL_TEES"]),
    ("Building Mix", ["TYPE1_TOP_FIT_CHOICES", "LANDMARK_SPACING", "BANNED_BUILDINGS"]),
]

PREVIEW_SLIDER_RANGES = {
    "GAP_BIG": (2, 10),
    "GAP_SMALL": (2, 10),
    "PAD_BIG": (2, 10),
    "PAD_SMALL": (2, 10),
    "N_BIG_CORNERS": (0, 10),
    "N_SMALL_CORNERS": (0, 10),
    "N_BIG_TEES": (0, 10),
    "N_SMALL_TEES": (0, 10),
    "TYPE1_TOP_FIT_CHOICES": (1, 10),
    "LANDMARK_SPACING": (1, 10),
}

CANVAS_SIZE_OPTIONS = {
    "Very Small": "40",
    "Small": "60",
    "Normal": "80",
    "Big": "100",
    "Very Big": "120",
}
CLEARANCE_OPTIONS = {
    "Very Dense": "3",
    "Dense": "4",
    "Normal": "5",
    "Sparse": "6",
    "Very Sparse": "7",
}

def grid_preview_path(seed):
    return os.path.join(PREVIEW_GRID, f"seed_{seed}.png")


def city_preview_path(seed):
    return os.path.join(PREVIEW_CITY, f"seed_{seed}.png")


def city_render_path(seed):
    return os.path.join(CITY_RENDERS, f"seed_{seed}.png")


def extracted_assets_ready():
    return os.path.exists(ROAD_CONTACT_SHEET) and os.path.exists(BUILD_CONTACT_SHEET)


def region_to_xyz_pair(region):
    if isinstance(region, BuildRegion):
        return region.bounds.as_xyz_pair()
    if isinstance(region, BlockRegion):
        return region.as_xyz_pair()
    raise TypeError(f"Unsupported region type: {type(region).__name__}")


def first_build_region(build_types, build_type):
    for region in build_types:
        region_type = region.build_type if isinstance(region, BuildRegion) else region[0]
        if region_type == build_type:
            return region
    return BuildRegion(build_type, BlockRegion(0, 0, 0, 0, 64, 64))


# Config values the header row exposes as labelled selectors rather than raw
# integers. Maps config name -> (label->value options, human-facing name).
SELECTOR_OPTIONS = {
    "FINE": (CANVAS_SIZE_OPTIONS, "City Size"),
    "GAP_MIXED": (CLEARANCE_OPTIONS, "Grid Density"),
}


def selector_value(name, label):
    """Resolve a selector label (e.g. 'Small') to its numeric config value."""
    options, human = SELECTOR_OPTIONS[name]
    try:
        return options[label]
    except KeyError as exc:
        raise ConfigError(f"{human} must be one of the selector values.") from exc


def selector_label(name, value):
    """Resolve a numeric config value back to its selector label, or None."""
    options, _human = SELECTOR_OPTIONS[name]
    for label, numeric in options.items():
        if str(value) == numeric:
            return label
    return None


def config_default(name):
    value = getattr(algo, name)
    if isinstance(value, set):
        return ", ".join(sorted(value))
    if name in SELECTOR_OPTIONS:
        label = selector_label(name, value)
        if label is not None:
            return label
    return str(value)


def algo_defaults_snapshot():
    return {name: config_default(name) for name, _label, _description in PREVIEW_CONFIGS}


def create_config_values(initial=None):
    values = algo_defaults_snapshot()
    if initial:
        for name in values:
            if name in initial:
                values[name] = str(initial[name])
    return values


def snapshot_config_values(config_values):
    return {
        name: str(config_values[name]).strip()
        for name, _label, _description in PREVIEW_CONFIGS
    }


def build_algo_env_from_values(config_values):
    normalized = snapshot_config_values(config_values)
    env = {}
    for name, _label, _description in PREVIEW_CONFIGS:
        value = normalized[name]
        if name == "BANNED_BUILDINGS":
            env[f"MC_CITY_{name}"] = value
            continue
        if name in SELECTOR_OPTIONS:
            value = selector_value(name, value)
        try:
            int(value)
        except ValueError as exc:
            raise ConfigError(f"{name} must be an integer.") from exc
        env[f"MC_CITY_{name}"] = value
    return env


def default_algo_tab_config():
    return {
        "seed": str(DEFAULT_SEED),
        "algo": algo_defaults_snapshot(),
    }


def _serialize_xyz_pair(start, end):
    return {
        "start": list(start),
        "end": list(end),
    }


def default_extraction_tab_config():
    road_start, road_end = region_to_xyz_pair(ROAD_BOX)
    house_start, house_end = region_to_xyz_pair(first_build_region(BUILD_TYPES, 1))
    landmark_start, landmark_end = region_to_xyz_pair(first_build_region(BUILD_TYPES, 2))
    return {
        "world_path": SAVE,
        "target_version": AUTO_VERSION,
        "road": _serialize_xyz_pair(road_start, road_end),
        "house": _serialize_xyz_pair(house_start, house_end),
        "landmark": _serialize_xyz_pair(landmark_start, landmark_end),
    }


# Sentinel meaning "no explicit paste target chosen" in the selector.
AUTO_VERSION = "auto"


def version_selector_items(min_data_version=None):
    """(label, value) pairs for the paste-target dropdown, newest first.

    Indicator only: it lists the Minecraft versions the output can be pasted into
    -- the source version and newer -- so the user can confirm the target. It
    does not affect the stamp, which is always the source version (see
    source_stamp_data_version). When min_data_version is given, only versions at
    or above it are listed.
    """
    items = [("Auto", AUTO_VERSION)]
    items.extend(
        (name, name)
        for dv, name in sorted(RELEASE_NAMES.items(), reverse=True)
        if min_data_version is None or dv >= min_data_version
    )
    return items


def source_stamp_data_version(world_path):
    """DataVersion to stamp on outputs: the source world's own version.

    Outputs are always stamped with the source world's version (clamped to the
    hard floor) so forward-only compatibility stays anchored to the source data.
    Stamping any newer version would risk skipping rename/upgrade steps for
    blocks that changed after the source version.
    """
    detected = detect_world_data_version(world_path)
    resolved = detected if detected is not None else HARD_FLOOR_DATA_VERSION
    return max(resolved, HARD_FLOOR_DATA_VERSION)


def stamp_version_env(world_path):
    """Env fragment pinning MC_CITY_DATA_VERSION to the source world's version.

    Always explicit so stages that do not set MC_CITY_SAVE (construct, render)
    stamp the source version instead of re-detecting the wrong (default) world.
    """
    return {"MC_CITY_DATA_VERSION": str(source_stamp_data_version(world_path))}


def load_saved_gui_config():
    if not os.path.exists(SAVED_GUI_CONFIG_PATH) and os.path.exists(LEGACY_SAVED_GUI_CONFIG_PATH):
        try:
            os.makedirs(os.path.dirname(SAVED_GUI_CONFIG_PATH), exist_ok=True)
            os.replace(LEGACY_SAVED_GUI_CONFIG_PATH, SAVED_GUI_CONFIG_PATH)
        except OSError:
            pass
    if not os.path.exists(SAVED_GUI_CONFIG_PATH):
        return {}
    try:
        with open(SAVED_GUI_CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_saved_gui_config(config):
    os.makedirs(os.path.dirname(SAVED_GUI_CONFIG_PATH), exist_ok=True)
    with open(SAVED_GUI_CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)


def save_progress_timing(section, payload):
    """Persist latest progress timing diagnostics for weight tuning."""
    os.makedirs(os.path.dirname(PROGRESS_TIMINGS_PATH), exist_ok=True)
    data = {}
    if os.path.exists(PROGRESS_TIMINGS_PATH):
        try:
            with open(PROGRESS_TIMINGS_PATH, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError):
            data = {}
    data[section] = payload
    with open(PROGRESS_TIMINGS_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def validate_seed(seed):
    try:
        int(seed)
    except ValueError as exc:
        raise SeedError("Seed must be an integer.") from exc


def open_in_file_manager(path):
    target = os.path.abspath(path)
    if sys.platform.startswith("win"):
        os.startfile(target)
        return
    command = ["open", target] if sys.platform == "darwin" else ["xdg-open", target]
    subprocess.Popen(command)


def _remove_file(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _clear_dir(directory):
    if os.path.isdir(directory):
        for path in glob.glob(os.path.join(directory, "*")):
            _remove_file(path)


def clear_preview_cache():
    """Delete all cached world top-down preview images (artifacts/world_preview/)."""
    _clear_dir(os.path.join(ARTIFACTS, "world_preview"))


def clear_pipeline_artifacts():
    """Wipe every pipeline artifact but keep exported worlds (05_world/saves/).

    Shared by app launch and switching worlds so both start from the same clean
    slate; only the standalone worlds under saves/ survive.
    """
    if not os.path.isdir(ARTIFACTS):
        return
    keep = os.path.normpath(SAVES)
    for entry in os.listdir(ARTIFACTS):
        path = os.path.join(ARTIFACTS, entry)
        normalized = os.path.normpath(path)
        if normalized == keep:
            continue
        if os.path.isdir(path):
            if keep.startswith(normalized + os.sep):
                for child in os.listdir(path):
                    child_path = os.path.join(path, child)
                    if os.path.normpath(child_path) == keep:
                        continue
                    if os.path.isdir(child_path):
                        shutil.rmtree(child_path, ignore_errors=True)
                    else:
                        _remove_file(child_path)
            else:
                shutil.rmtree(path, ignore_errors=True)
        else:
            _remove_file(path)
