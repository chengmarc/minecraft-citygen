"""Minecraft version info: DataVersion detection and release-name labels.

CityGen does no version *conversion* of its own -- this is not a compatibility
layer. Blocks are copied verbatim from the source world into the output
schematic, which is stamped with the source world's own DataVersion; downstream
import or load tooling handles any forward upgrade. So all this module needs to do is:

* read the source world's DataVersion from its ``level.dat``
  (``detect_world_data_version``),
* map DataVersions to human release names for display in the GUI
  (``RELEASE_NAMES`` / ``release_name_for``), and
* record the minimum version CityGen supports (``HARD_FLOOR_DATA_VERSION``).

The floor is 26.1.2: the bundled source world and authored asset format target
that version or newer.
"""
from __future__ import annotations

import os

import nbtlib

# Forward-only compatibility floor. Older schematics can be upgraded forward into
# newer Minecraft versions, but backward is impossible, so every stamp is clamped
# up to this floor.
HARD_FLOOR_DATA_VERSION = 4790  # Minecraft 26.1.2

# DataVersion -> Minecraft release name, used only to label the detected source
# world in the GUI. Hand-maintained (display only): add newer releases as they
# ship; an unknown DataVersion just falls back to its raw number, so a missing
# entry is purely cosmetic.
RELEASE_NAMES = {
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
