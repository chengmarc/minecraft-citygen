"""Files the GUI owns on disk: saved settings, the startup error log, and artifact cleanup."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from citygen.paths import APP_DATA, BUILDS_CONTACT_SHEET, ROADS_CONTACT_SHEET, ROOT, SAVES, SETTINGS

STARTUP_ERROR_LOG = os.path.join(ROOT, "application_startup_error.log")


def extracted_assets_ready():
    return os.path.exists(ROADS_CONTACT_SHEET) and os.path.exists(BUILDS_CONTACT_SHEET)


def load_saved_gui_config():
    if not os.path.exists(SETTINGS):
        return {}
    try:
        with open(SETTINGS, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_saved_gui_config(config):
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    with open(SETTINGS, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)


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
    settings = os.path.normpath(SETTINGS)
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
