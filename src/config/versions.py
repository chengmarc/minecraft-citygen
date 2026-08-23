"""Minecraft version info: DataVersion detection and release-name labels.

CityGen does no version *conversion* of its own -- this is not a compatibility
layer. Blocks are copied verbatim from the source world into the output
schematic, which is stamped with the source world's own DataVersion; WorldEdit's
DataFixer does any upgrade on paste. So all this module needs to do is:

* read the source world's DataVersion from its ``level.dat``
  (``detect_world_data_version``),
* map DataVersions to human release names for display in the GUI
  (``RELEASE_NAMES`` / ``release_name_for``), and
* record the minimum version CityGen supports (``HARD_FLOOR_DATA_VERSION``).

The floor is 1.20: the bundled source world is 1.20, and every output uses the
Sponge v3 container (WorldEdit 7.3.0+, Minecraft 1.20+).
"""
from __future__ import annotations

import os

import nbtlib

# Forward-only compatibility floor. Forward compat is free -- WorldEdit upgrades
# an older schematic forward into a newer world -- but backward is impossible, so
# every stamp is clamped up to this floor. The floor is 1.20: the bundled source
# world is 1.20, and outputs always use the Sponge v3 container, which pre-1.20
# WorldEdit (7.2.x) cannot read anyway.
HARD_FLOOR_DATA_VERSION = 3463  # Minecraft 1.20

# DataVersion -> Minecraft release name, used only to label the detected source
# world in the GUI. Hand-maintained (display only): add newer releases as they
# ship; an unknown DataVersion just falls back to its raw number, so a missing
# entry is purely cosmetic.
RELEASE_NAMES = {
    3337: "1.19.4",
    3463: "1.20",
    3465: "1.20.1",
    3578: "1.20.2",
    3698: "1.20.3",
    3700: "1.20.4",
    3837: "1.20.5",
    3839: "1.20.6",
    3953: "1.21",
    3955: "1.21.1",
    4080: "1.21.2",
    4082: "1.21.3",
    4189: "1.21.4",
    4325: "1.21.5",
    4435: "1.21.6",
    4438: "1.21.7",
    4440: "1.21.8",
    4554: "1.21.9",
    4556: "1.21.10",
    4671: "1.21.11",
    4786: "26.1",
    4788: "26.1.1",
    4790: "26.1.2",
    4903: "26.2",
}


def release_name_for(data_version: int) -> str:
    """Human release label for a DataVersion, for display only.

    Returns the exact release name when known, else the raw DataVersion so an
    unmapped (older or newer) world still shows something meaningful.
    """
    return RELEASE_NAMES.get(data_version) or f"DataVersion {data_version}"


def detect_world_data_version(save_path: str) -> int | None:
    """Read ``Data.DataVersion`` from a world's ``level.dat``, or None.

    Authoritative for the source world's own version. Tolerant of a
    missing/unreadable file so a trimmed world falls back cleanly.
    """
    if not save_path:
        return None
    level_dat = os.path.join(save_path, "level.dat")
    if not os.path.isfile(level_dat):
        return None
    try:
        data = nbtlib.load(level_dat).get("Data")
        if data is None:
            return None
        version = data.get("DataVersion")
        return int(version) if version is not None else None
    except (OSError, KeyError, ValueError):
        return None
