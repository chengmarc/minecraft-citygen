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
    ARTIFACTS, BUILD_CATALOG, BUILDS_PROD, CITY_PROD, CITY_SIM,
    GRID_SIM, GUI, ROOT, ROADS_PROD, SAVES,
)
from config.world import BUILD_TYPES, ROAD_BOX, SAVE
from config.models import BlockRegion, BuildRegion
from config.versions import HARD_FLOOR_DATA_VERSION, RELEASE_NAMES, detect_world_data_version, release_name_for


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
    ("TYPE2_TOP_FIT_CHOICES", "Landmark Style Variety", "Higher values mix in more different landmark designs."),
    ("TYPE2_SAME_COARSE_SPAN", "Landmark Repeat Distance", "Higher values spread repeated landmarks farther apart."),
]
PREVIEW_CONFIG_LOOKUP = {name: (label, description) for name, label, description in PREVIEW_CONFIGS}

PREVIEW_CONFIG_GROUPS = [
    ("Avenue and Street Spacing", ["GAP_BIG", "PAD_BIG", "GAP_SMALL", "PAD_SMALL"]),
    ("Avenue and Street Shape", ["N_BIG_CORNERS", "N_BIG_TEES", "N_SMALL_CORNERS", "N_SMALL_TEES"]),
    ("Building Mix", ["BANNED_BUILDINGS", "TYPE1_TOP_FIT_CHOICES", "TYPE2_TOP_FIT_CHOICES", "TYPE2_SAME_COARSE_SPAN"]),
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
    ("pipeline.01_roads.simulation", 15),
    ("pipeline.02_builds.simulation", 20),
    ("pipeline.03_grid.simulation", 30),
    ("pipeline.04_city.simulation", 35),
]

# Per-step weights for the Generation-tab progress bar. The Generate button runs
# three stages back to back: construct the .schem, render the isometric PNG, then
# export the standalone world. Eight entries cover the eight city_construct work
# segments (steps 0→1 through 7→8); the other two cover the render and world stages.
GENERATION_CONSTRUCT_WEIGHTS = [3, 4, 2, 8, 18, 12, 8, 8]   # sum = 63
GENERATION_RENDER_WEIGHT = 37
GENERATION_WORLD_WEIGHT = 20

# Per-stage weights for the extraction-tab progress bar, in run order: roads
# extract, roads render, builds extract, builds render. The scanning-heavy
# extract passes carry more weight than the contact-sheet render passes. Used as
# one continuous weighted bar so it advances across all four stages instead of
# resetting per stage.
EXTRACT_STAGE_WEIGHTS = [20, 10, 45, 25]   # sum = 100

# A stage can run several work phases with different totals (e.g. a fast "scan"
# then a slow "export"). Each phase fills this fraction of the segment room still
# left, so a later phase always has room to keep advancing smoothly instead of
# freezing at the segment top.
EXTRACT_PHASE_FILL = 0.7

# How far the animated ("fake") progress creeps into the current step's segment
# before stalling to wait for the stage to actually finish.
SCRIPT_PROGRESS_HEADROOM = 0.90
# Per-tick easing rate of that animation: each tick advances this fraction of the
# remaining distance to the soft target (every SCRIPT_PROGRESS_TICK_MS ms).
SCRIPT_PROGRESS_RATE = 0.10
SCRIPT_PROGRESS_TICK_MS = 120


def stage_script_label(module):
    """Stage module path -> script path for status display.

    ``'pipeline.04_city.construct'`` -> ``'pipeline/04_city/construct.py'``.
    """
    return module.replace(".", "/") + ".py"


def format_stage_status(step, total_steps, module, annotation=""):
    """Consistent progress status shared by the Preview and Generation tabs.

    ``'Stage 1/2 - pipeline/04_city/construct.py - Writing schematic'``. The
    trailing annotation is omitted when empty.
    """
    status = f"Stage {step}/{total_steps} - {stage_script_label(module)}"
    annotation = (annotation or "").strip()
    return f"{status} - {annotation}" if annotation else status


def grid_preview_path(seed):
    return os.path.join(GRID_SIM, f"seed_{seed}_preview.png")


def city_preview_path(seed):
    return os.path.join(CITY_SIM, f"seed_{seed}.png")


def city_render_path(seed):
    return os.path.join(CITY_PROD, f"seed_{seed}.png")


def extracted_assets_ready():
    required = (ROAD_CONTACT_SHEET, BUILD_CONTACT_SHEET, BUILD_CATALOG)
    if not all(os.path.exists(path) for path in required):
        return False
    road_assets = glob.glob(os.path.join(ROADS_PROD, "*.schem"))
    build_assets = glob.glob(os.path.join(BUILDS_PROD, "*.schem"))
    return bool(road_assets) and bool(build_assets)


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
    """Wipe every pipeline artifact but keep exported worlds (saves/).

    Shared by app launch and switching worlds so both start from the same clean
    slate; only the standalone worlds under saves/ survive.
    """
    if not os.path.isdir(ARTIFACTS):
        return
    keep = os.path.normpath(SAVES)
    for entry in os.listdir(ARTIFACTS):
        path = os.path.join(ARTIFACTS, entry)
        if os.path.normpath(path) == keep:
            continue
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            _remove_file(path)
