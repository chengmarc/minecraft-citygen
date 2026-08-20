"""Shared Qt-era GUI constants and non-widget helpers."""

from __future__ import annotations

import json
import os
import subprocess
import sys

from config import config_algo
from config.config_algo import DEFAULT_SEED
from config.config_path import BUILDS_PROD, CITY_PROD, CITY_SIM, GRID_SIM, GUI, ROOT, ROADS_PROD
from config.config_world import BUILD_TYPES, ROAD_BOX, SAVE
from config.models import BlockRegion, BuildRegion


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
        "road": _serialize_xyz_pair(road_start, road_end),
        "house": _serialize_xyz_pair(house_start, house_end),
        "landmark": _serialize_xyz_pair(landmark_start, landmark_end),
    }


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
