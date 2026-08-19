"""Environment diagnostics for first-run setup."""

from __future__ import annotations

import importlib.util
import os
import platform
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.config_path import DEFAULT_WORLD, RESOURCE_ROOT, ROOT, WORLDEDIT_SCHEM
from config.config_world import REGION_DIR, REGION_DIR_CANDIDATES, SAVE


def _module_status(name: str) -> tuple[bool, str]:
    found = importlib.util.find_spec(name) is not None
    return found, ("ok" if found else "missing")


def _print_path(label: str, value: str, *, exists: bool | None = None) -> None:
    status = ""
    if exists is True:
        status = " [exists]"
    elif exists is False:
        status = " [missing]"
    print(f"{label}: {value or '<not set>'}{status}")


def main() -> int:
    print("CityGen environment doctor")
    print(f"python: {sys.version.split()[0]} ({platform.platform()})")
    print(f"executable: {sys.executable}")
    _print_path("app root", ROOT, exists=os.path.isdir(ROOT))
    _print_path("resource root", RESOURCE_ROOT, exists=os.path.isdir(RESOURCE_ROOT))
    print()

    missing = False
    print("Dependencies")
    for module_name in ("PIL", "numpy", "nbtlib", "tkinter"):
        found, status = _module_status(module_name)
        print(f"- {module_name}: {status}")
        missing = missing or not found
    print()

    print("Paths")
    _print_path("save", SAVE, exists=bool(SAVE) and os.path.isdir(SAVE))
    _print_path("bundled default world", DEFAULT_WORLD, exists=os.path.isdir(DEFAULT_WORLD))
    _print_path("region", REGION_DIR, exists=bool(REGION_DIR) and os.path.isdir(REGION_DIR))
    _print_path("worldedit schematics", WORLDEDIT_SCHEM, exists=os.path.isdir(WORLDEDIT_SCHEM))
    if REGION_DIR_CANDIDATES:
        print("region candidates:")
        for candidate in REGION_DIR_CANDIDATES:
            print(f"- {candidate}")
    print()

    if not SAVE or not os.path.isdir(REGION_DIR):
        print("Action: set MC_CITY_SAVE to your Minecraft world folder or paste it into the Extraction tab.")
    if not os.path.isdir(WORLDEDIT_SCHEM):
        print("Action: set MC_CITY_WORLDEDIT_SCHEM if you want exports copied somewhere other than artifacts/worldedit.")

    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
