"""Files the GUI owns on disk: icons, saved settings, timings, and artifact cleanup."""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys

from config.path import ARTIFACTS, BUILDS_CONTACT_SHEET, GUI, ROADS_CONTACT_SHEET, ROOT, SAVES, WORLD_PREVIEW_CACHE


ICON_DIR = os.path.join(GUI, "icons")
APP_ICON_PATH = os.path.join(ICON_DIR, "app-icon.png")
STARTUP_ERROR_LOG = os.path.join(ROOT, "application_startup_error.log")
PROGRESS_TIMINGS_PATH = os.path.join(ARTIFACTS, "progress_timings.json")
LEGACY_SAVED_GUI_CONFIG_PATH = os.path.join(ROOT, "citygen_saved_config.json")
SAVED_GUI_CONFIG_PATH = os.path.join(ROOT, "src", "config", "citygen.json")


def extracted_assets_ready():
    return os.path.exists(ROADS_CONTACT_SHEET) and os.path.exists(BUILDS_CONTACT_SHEET)


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
    """Delete all cached world top-down preview images."""
    _clear_dir(WORLD_PREVIEW_CACHE)


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
