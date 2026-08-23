"""Minecraft version / DataVersion helpers.

CityGen copies block strings straight from the source world into the output
Sponge schematic, so block *content* is version-transparent. The one thing that
is not transparent is the ``DataVersion`` stamped on the schematic: WorldEdit
upgrades an older schematic forward into a newer world, but cannot downgrade a
newer one.

CityGen therefore commits to *forward-only* compatibility. Outputs are always
stamped with the source world's own DataVersion (read from its ``level.dat``),
clamped up to the 1.19.4 hard floor (``HARD_FLOOR_DATA_VERSION``): the bundled
assets need 1.19.4 blocks (cherry wood, pink petals) and it is the oldest target
the Sponge v2 container still reaches. WorldEdit's DataFixer then upgrades the
schematic forward on paste, so there is no release table or per-block map to
maintain -- just the source world's own version.
"""
from __future__ import annotations

import os

import nbtlib

# Forward-only compatibility floor. Forward compat is free -- WorldEdit upgrades
# an older schematic forward into a newer world -- but backward is impossible, so
# every stamp is clamped up to this floor. 1.19.4 is where the two binding
# constraints bottom out: the bundled assets need 1.19.4 blocks (cherry wood,
# pink petals), and it is the newest version still served by the Sponge v2
# container that pre-1.20 WorldEdit (7.2.x) can read.
HARD_FLOOR_DATA_VERSION = 3337  # Minecraft 1.19.4


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
