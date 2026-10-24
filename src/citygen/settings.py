"""What a run is set up with: the algorithm's knobs, the source world and its sample areas, and the version stamp.

:class:`Algo` holds the per-run knobs; the generator takes one as an argument and never reads :data:`ALGO`, which is
only the defaults the form starts from.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

import nbtlib

from citygen.paths import DEFAULT_WORLD

CELL = 9  # simulation pixels and production blocks per fine cell; fixed by the asset geometry
DEFAULT_SEED = 5


@dataclass(frozen=True)
class Algo:
    fine: int = 80  # fine grid edge (fine x fine cells); rounded down to even, since coarse = fine // 2

    # forced gap between parallel lines
    gap_mixed: int = 5  # fine-cell clearance between a small street and a big corridor band
    gap_big: int = 5  # coarse-cell spacing step between big avenues (higher = fewer big roads)
    gap_small: int = 5  # min fine-cell spacing between small streets (lower = more small roads)

    # forced padding from canvas edge
    pad_big: int = 5  # coarse-cell padding for big road positions from the grid edge
    pad_small: int = 5  # fine-cell padding for small road positions from the grid edge

    # forced L-corners and T-intersections
    n_big_corners: int = 5
    n_small_corners: int = 5
    n_big_tees: int = 5
    n_small_tees: int = 5

    banned_buildings: frozenset[str] = frozenset()  # building IDs to skip during placement
    landmark_spacing: int = 5  # min fine-cell distance between landmark footprints
    type1_top_fit_choices: int = 5  # each type-1 frontage point picks randomly among this many best fits


ALGO = Algo()


# --- The source world: its sample areas, and the version the outputs are stamped with


def _coerce_xyz_point(values: Iterable[int]) -> tuple[int, int, int]:
    values = tuple(values)
    if len(values) != 3:
        raise ValueError(f"expected 3 values, got {len(values)}")
    return tuple(int(value) for value in values)


@dataclass(frozen=True, slots=True)
class VerticalRange:
    start: int
    end: int

    def __post_init__(self) -> None:
        lo, hi = sorted((int(self.start), int(self.end)))
        object.__setattr__(self, "start", lo)
        object.__setattr__(self, "end", hi)

    def as_tuple(self) -> tuple[int, int]:
        return self.start, self.end


@dataclass(frozen=True, slots=True)
class BlockRegion:
    x0: int
    x1: int
    z0: int
    z1: int
    y0: int
    y1: int

    def __post_init__(self) -> None:
        x0, x1 = sorted((int(self.x0), int(self.x1)))
        z0, z1 = sorted((int(self.z0), int(self.z1)))
        y0, y1 = sorted((int(self.y0), int(self.y1)))
        object.__setattr__(self, "x0", x0)
        object.__setattr__(self, "x1", x1)
        object.__setattr__(self, "z0", z0)
        object.__setattr__(self, "z1", z1)
        object.__setattr__(self, "y0", y0)
        object.__setattr__(self, "y1", y1)

    @classmethod
    def from_xyz_pair(
        cls,
        start: tuple[int, int, int] | list[int],
        end: tuple[int, int, int] | list[int],
    ) -> "BlockRegion":
        x0, y0, z0 = _coerce_xyz_point(start)
        x1, y1, z1 = _coerce_xyz_point(end)
        return cls(x0, x1, z0, z1, y0, y1)

    def as_tuple(self) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        return self.as_xyz_pair()

    def as_xyz_pair(self) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        return (self.x0, self.y0, self.z0), (self.x1, self.y1, self.z1)


@dataclass(frozen=True, slots=True)
class BuildRegion:
    build_type: int
    bounds: BlockRegion

    def as_tuple(self) -> tuple[int, tuple[int, int, int], tuple[int, int, int]]:
        start, end = self.bounds.as_xyz_pair()
        return self.build_type, start, end


# Forward-only compatibility floor. Older schematics can be upgraded forward into
# newer MC versions, but backward is impossible, so every stamp is clamped
# up to this floor.
HARD_FLOOR_DATA_VERSION = 4790  # MC 26.1.2

# DataVersion -> MC release name, used only to label the detected source
# world in the GUI. Hand-maintained (display only): add newer releases as they
# ship; an unknown DataVersion just falls back to its raw number, so a missing
# entry is purely cosmetic.
RELEASE_NAMES = {
    4790: "26.1.2",
    4903: "26.2",
}


def release_name_for(data_version: int) -> str:
    """Human release label for a DataVersion, for display only."""
    return RELEASE_NAMES.get(data_version) or f"DataVersion {data_version}"


def detect_world_data_version(save_path: str) -> int | None:
    """Read ``Data.DataVersion`` from a world's ``level.dat``, or None."""
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


def source_data_version(save_path: str | None) -> int:
    """DataVersion every output is stamped with: the source world's own, clamped up to the floor.

    Stamping any newer version would skip rename/upgrade steps for blocks that
    changed after the source version (forward-only compatibility).
    """
    detected = detect_world_data_version(save_path)
    resolved = detected if detected is not None else HARD_FLOOR_DATA_VERSION
    return max(resolved, HARD_FLOOR_DATA_VERSION)


SAVE = DEFAULT_WORLD

ROAD_BOX = BlockRegion.from_xyz_pair((-80, 65, 16), (-17, 75, 127))

# Build regions' y0/y1 is retained as catalog metadata; marker blocks define extracted geometry.
BUILD_TYPES = (
    BuildRegion(1, BlockRegion.from_xyz_pair((-384, 64, -192), (-17, 65, -17))),
    BuildRegion(2, BlockRegion.from_xyz_pair((16, 64, -320), (351, 65, 143))),
)

BUILD_MARKER_Y_RANGE = VerticalRange(60, 230)
