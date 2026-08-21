"""Shared Qt-era GUI constants and non-widget helpers."""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

import nbtlib

from config import config_algo
from config.config_algo import DEFAULT_SEED
from config.config_path import (
    ARTIFACTS, BUILDS_PROD, BUILDS_SIM, CITY_PROD, CITY_SIM,
    GRID_PROD, GRID_SIM, GUI, ROOT, ROADS_PROD, ROADS_SIM,
)
from config.config_world import BUILD_TYPES, ROAD_BOX, SAVE
from config.models import BlockRegion, BuildRegion
from config.version_compat import (
    FALLBACK_DATA_VERSION,
    RELEASES,
    SUPPORTED_FLOOR,
    compatibility_report,
    data_version_for,
    detect_world_data_version,
    release_name_for,
)


class SeedError(ValueError):
    """Raised when the seed field does not hold a valid integer."""


class ConfigError(ValueError):
    """Raised when an algorithm/city config value is invalid."""


ROOT_DIR = ROOT
ICON_DIR = os.path.join(GUI, "icons")
CONFIG_DIR = os.path.join(ROOT_DIR, "src", "config")
APP_ICON_PATH = os.path.join(ICON_DIR, "app-icon.png")
ROAD_CONTACT_SHEET = os.path.join(ROADS_PROD, "_contact_sheet.png")
BUILD_CONTACT_SHEET = os.path.join(BUILDS_PROD, "_contact_sheet.png")

APP_WIDTH = 1366
APP_HEIGHT = 768
STARTUP_ERROR_LOG = os.path.join(ROOT_DIR, "application_startup_error.log")
LEGACY_SAVED_GUI_CONFIG_PATH = os.path.join(ROOT_DIR, "citygen_saved_config.json")
SAVED_GUI_CONFIG_PATH = os.path.join(CONFIG_DIR, "config_citygen.json")

PREVIEW_CONFIGS = [
    ("FINE", "City Size", "Fine-cell width and height of the generated map."),
    ("GAP_MIXED", "Grid Density", "Minimum clearance between a small street and a big avenue band."),
    ("GAP_BIG", "Avenue Spacing", "Coarse-cell spacing between avenues. Higher means fewer avenues."),
    ("PAD_BIG", "Avenue Padding", "Coarse-cell margin that keeps avenues away from the edge."),
    ("GAP_SMALL", "Street Spacing", "Fine-cell spacing between streets. Lower means more streets."),
    ("PAD_SMALL", "Street Padding", "Fine-cell margin that keeps streets away from the edge."),
    ("N_BIG_CORNERS", "Avenue L-corners", "Forced L-corner count in the avenue network."),
    ("N_BIG_TEES", "Avenue T-intersections", "Forced T-intersection count in the avenue network."),
    ("N_SMALL_CORNERS", "Street L-corners", "Forced L-corner count in the street network."),
    ("N_SMALL_TEES", "Street T-intersections", "Forced T-intersection count in the street network."),
    ("BANNED_BUILDINGS", "Banned Buildings", "Comma-separated house or landmark IDs skipped during city placement."),
    ("TYPE1_TOP_FIT_CHOICES", "House Variety", "Higher values allow more eligible house designs to appear in similar street lots."),
    ("TYPE2_TOP_FIT_CHOICES", "Landmark Variety", "Higher values allow more eligible landmark designs to appear along avenue frontage."),
    ("TYPE2_SAME_COARSE_SPAN", "Landmark Separation", "Controls how far apart repeated landmark designs must be. Higher values spread repeated landmarks farther apart."),
]
PREVIEW_CONFIG_LOOKUP = {name: (label, description) for name, label, description in PREVIEW_CONFIGS}

PREVIEW_CONFIG_GROUPS = [
    ("Spacing and Padding", ["GAP_BIG", "PAD_BIG", "GAP_SMALL", "PAD_SMALL"]),
    ("Corners and Tees", ["N_BIG_CORNERS", "N_BIG_TEES", "N_SMALL_CORNERS", "N_SMALL_TEES"]),
    ("Building Placement", ["BANNED_BUILDINGS", "TYPE1_TOP_FIT_CHOICES", "TYPE2_TOP_FIT_CHOICES", "TYPE2_SAME_COARSE_SPAN"]),
]

PREVIEW_SLIDER_RANGES = {
    "GAP_BIG": (6, 10),
    "GAP_SMALL": (2, 6),
    "PAD_BIG": (2, 6),
    "PAD_SMALL": (4, 8),
    "N_BIG_CORNERS": (0, 12),
    "N_SMALL_CORNERS": (0, 12),
    "N_BIG_TEES": (0, 12),
    "N_SMALL_TEES": (0, 12),
    "TYPE1_TOP_FIT_CHOICES": (5, 9),
    "TYPE2_TOP_FIT_CHOICES": (1, 5),
    "TYPE2_SAME_COARSE_SPAN": (4, 8),
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

PREVIEW_PROGRESS_WEIGHTS = [
    ("pipeline.01_roads_simulation", 15),
    ("pipeline.02_builds_simulation", 20),
    ("pipeline.03_grid_simulation", 30),
    ("pipeline.04_city_simulation", 35),
]
RENDER_PROGRESS_WEIGHTS = [
    ("pipeline.04_city_construct", 60),
    ("pipeline.04_city_render", 40),
]

SCRIPT_PROGRESS_HEADROOM = 0.88
SCRIPT_PROGRESS_TICK_MS = 120


def grid_preview_path(seed):
    return os.path.join(GRID_SIM, f"seed_{seed}_preview.png")


def city_preview_path(seed):
    return os.path.join(CITY_SIM, f"seed_{seed}.png")


def city_render_path(seed):
    return os.path.join(CITY_PROD, f"seed_{seed}.png")


def format_xyz(pos):
    return ", ".join(str(value) for value in pos)


def parse_xyz(value, label):
    value = value.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    parts = [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    if len(parts) != 3:
        raise ValueError(f"{label} must be three values: x, y, z")
    try:
        return tuple(int(part) for part in parts)
    except ValueError as exc:
        raise ValueError(f"{label} must contain only integers.") from exc


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
    value = getattr(config_algo, name)
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
    env = os.environ.copy()
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


# Sentinel stored in config when the target version tracks the source world.
AUTO_VERSION = "auto"


def version_selector_items(min_data_version=None):
    """(label, value) pairs for the target-version dropdown, newest first.

    If min_data_version is given, only versions at or above it are included.
    """
    items = [("Auto", AUTO_VERSION)]
    items.extend(
        (name, name) for name, ver in reversed(RELEASES)
        if min_data_version is None or ver >= min_data_version
    )
    return items


def resolve_target_data_version(world_path, choice):
    """Resolve a stored version choice to a concrete DataVersion int.

    ``auto`` detects the source world's own version (fallback if unreadable);
    any other value is a known release name.
    """
    if choice and choice != AUTO_VERSION:
        known = data_version_for(choice)
        if known is not None:
            return known
    detected = detect_world_data_version(world_path)
    resolved = detected if detected is not None else FALLBACK_DATA_VERSION
    # Never target below the hard floor, even if the source world is older.
    return max(resolved, SUPPORTED_FLOOR)


def target_version_env(world_path, choice):
    """Env fragment pinning MC_CITY_DATA_VERSION for a stage run.

    Always explicit (even in auto mode) so stages that do not set MC_CITY_SAVE
    still stamp the intended version instead of re-detecting the wrong world.
    """
    return {"MC_CITY_DATA_VERSION": str(resolve_target_data_version(world_path, choice))}


def target_version_summary(world_path, choice):
    """Short human label for the resolved target, e.g. 'Auto -> 1.19.4'."""
    resolved = resolve_target_data_version(world_path, choice)
    name = release_name_for(resolved)
    return f"Auto -> {name}" if choice == AUTO_VERSION else name


def _schem_palette_states(path):
    """Block-state strings in a Sponge .schem palette, or () if unreadable."""
    try:
        root = nbtlib.load(path)
    except (OSError, ValueError, KeyError):
        return ()
    schem = root.get("Schematic", root)
    blocks = schem.get("Blocks")
    palette = blocks.get("Palette") if blocks is not None else schem.get("Palette")
    return tuple(str(key) for key in palette) if palette else ()


def extracted_asset_block_ids():
    """Union of block states across every extracted road/build .schem on disk.

    This is the true output palette the final city is assembled from, so it is
    the authoritative input for version-compatibility warnings. Returns an empty
    set when nothing has been extracted yet.
    """
    states = set()
    for base in (ROADS_PROD, BUILDS_PROD):
        for path in glob.glob(os.path.join(base, "*.schem")):
            states.update(_schem_palette_states(path))
    return states


def target_version_report(world_path, choice, block_states):
    """Compatibility report for these blocks against the chosen target version."""
    target = resolve_target_data_version(world_path, choice)
    return compatibility_report(block_states, target)


def format_compat_details(report):
    """One line per unsupported block: 'minecraft:pale_oak_shelf  (needs 1.21.9)'."""
    return "\n".join(
        f"{item['block']}  (needs {item['min_release']})" for item in report["offending"]
    )


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
    """Delete all pipeline artifacts, keeping only final city .schem and .png outputs."""
    clear_preview_cache()
    for directory in (ROADS_SIM, ROADS_PROD, BUILDS_SIM, BUILDS_PROD, GRID_SIM, GRID_PROD, CITY_SIM):
        _clear_dir(directory)
    if os.path.isdir(CITY_PROD):
        for path in glob.glob(os.path.join(CITY_PROD, "*")):
            if not path.endswith((".schem", ".png")):
                _remove_file(path)
