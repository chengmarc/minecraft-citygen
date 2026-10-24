"""Files the GUI owns on disk: the window icon, saved settings, timings, and artifact cleanup."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from config.path import APP_DATA, APP_ICON, BUILDS_CONTACT_SHEET, ROADS_CONTACT_SHEET, ROOT, SAVES, SETTINGS


APP_ICON_PATH = APP_ICON
STARTUP_ERROR_LOG = os.path.join(ROOT, "application_startup_error.log")
PROGRESS_TIMINGS_PATH = os.path.join(APP_DATA, "progress_timings.json")
SAVED_GUI_CONFIG_PATH = SETTINGS


def extracted_assets_ready():
    return os.path.exists(ROADS_CONTACT_SHEET) and os.path.exists(BUILDS_CONTACT_SHEET)


def load_saved_gui_config():
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


def clear_pipeline_artifacts():
    """Wipe every pipeline artifact but keep exported worlds (05_world/saves/) and the saved settings.

    Shared by app launch and switching worlds so both start from the same clean
    slate; only the standalone worlds under saves/ and the settings survive.
    """
    if not os.path.isdir(APP_DATA):
        return
    keep = os.path.normpath(SAVES)
    settings = os.path.normpath(SAVED_GUI_CONFIG_PATH)
    for entry in os.listdir(APP_DATA):
        path = os.path.join(APP_DATA, entry)
        normalized = os.path.normpath(path)
        if normalized in (keep, settings):
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
