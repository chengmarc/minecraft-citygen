"""What a run is set up with: the algorithm's knobs, and the bundled world's sample areas.

:class:`Algo` holds the per-run knobs; the generator takes one as an argument and never reads :data:`ALGO`, which is
only the defaults the form starts from.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

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


# --- The sample areas


def _coerce_xyz_point(values: Iterable[int]) -> tuple[int, int, int]:
    values = tuple(values)
    if len(values) != 3:
        raise ValueError(f"expected 3 values, got {len(values)}")
    return tuple(int(value) for value in values)


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


@dataclass(frozen=True, slots=True)
class BuildRegion:
    build_type: int
    bounds: BlockRegion


# The bundled world's three sample areas, as the (start, end) block corners the Extract tab saves. Only x and z
# select: markers are found anywhere in BUILD_MARKER_Y_RANGE.
SAMPLE_AREAS = {
    "road": ((-80, 65, 16), (-17, 75, 127)),
    "house": ((-384, 64, -192), (-17, 65, -17)),
    "landmark": ((16, 64, -320), (351, 65, 143)),
}

BUILD_MARKER_Y_RANGE = (60, 230)
