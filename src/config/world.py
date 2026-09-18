"""World models, version labels, extraction regions, and save settings."""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from typing import Iterable

import nbtlib

from config.path import DEFAULT_WORLD, env_raw, env_str, region_dir_candidates, resolve_region_dir


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

    @classmethod
    def from_values(cls, values) -> "BlockRegion":
        values = tuple(values)
        if len(values) == 6:
            return cls(*(int(value) for value in values))
        if len(values) == 2:
            return cls.from_xyz_pair(values[0], values[1])
        raise ValueError(f"expected 6 flat values or 2 xyz points, got {len(values)}")

    def as_tuple(self) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        return self.as_xyz_pair()

    def as_flat_tuple(self) -> tuple[int, int, int, int, int, int]:
        return self.x0, self.x1, self.z0, self.z1, self.y0, self.y1

    def as_xyz_pair(self) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        return (self.x0, self.y0, self.z0), (self.x1, self.y1, self.z1)

    def to_env_value(self) -> str:
        start, end = self.as_xyz_pair()
        return f"({start}, {end})"


@dataclass(frozen=True, slots=True)
class BuildRegion:
    build_type: int
    bounds: BlockRegion

    @classmethod
    def from_values(cls, values) -> "BuildRegion":
        values = tuple(values)
        if len(values) == 7:
            build_type, *bounds = values
            return cls(int(build_type), BlockRegion.from_values(bounds))
        if len(values) == 3:
            build_type, start, end = values
            return cls(int(build_type), BlockRegion.from_xyz_pair(start, end))
        if len(values) == 2:
            build_type, bounds = values
            return cls(int(build_type), BlockRegion.from_values(bounds))
        raise ValueError(f"expected build type plus bounds, got {len(values)} values")

    def as_tuple(self) -> tuple[int, tuple[int, int, int], tuple[int, int, int]]:
        start, end = self.bounds.as_xyz_pair()
        return self.build_type, start, end

    def as_flat_tuple(self) -> tuple[int, int, int, int, int, int, int]:
        return (self.build_type, *self.bounds.as_flat_tuple())

    def to_env_value(self) -> str:
        return f"{self.build_type}, {self.bounds.to_env_value()}"


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


def _parse_tuple_like(value: str):
    parsed = ast.literal_eval(value)
    if isinstance(parsed, tuple):
        return parsed
    if isinstance(parsed, list):
        return tuple(parsed)
    raise ValueError(f"expected a tuple-like region value, got {type(parsed).__name__}")


def _parse_build_types(value: str) -> tuple[BuildRegion, ...]:
    return tuple(BuildRegion.from_values(_parse_tuple_like(item)) for item in value.split(";") if item.strip())


def _parse_block_region(value: str) -> BlockRegion:
    return BlockRegion.from_values(_parse_tuple_like(value))


def _env_block_region(name: str, default: BlockRegion) -> BlockRegion:
    raw = env_raw(name)
    return default if raw is None else _parse_block_region(raw)


def _env_build_regions(name: str, default: tuple[BuildRegion, ...]) -> tuple[BuildRegion, ...]:
    raw = env_raw(name)
    return default if raw is None else _parse_build_types(raw)


# Minecraft world save folder. Override with MC_CITY_SAVE when needed.
SAVE = env_str("SAVE", DEFAULT_WORLD)
REGION_DIR_CANDIDATES = tuple(region_dir_candidates(SAVE))
REGION_DIR = resolve_region_dir(SAVE)

# Schematic DataVersion. Forward-only compatibility means this is always the
# source world's own version, so schematic import stays aligned with the source
# data. Resolves to the GUI-pinned MC_CITY_DATA_VERSION (the source version, set
# explicitly because construct/render do not set MC_CITY_SAVE), else the source
# world's detected version, else the hard floor; always clamped up to the hard
# floor.
def _resolve_data_version() -> int:
    raw = env_raw("DATA_VERSION")
    if raw is not None:
        return max(int(raw.strip()), HARD_FLOOR_DATA_VERSION)
    return source_data_version(SAVE)


DATA_VERSION = _resolve_data_version()

# Road assets region in world ((x_a, y_a, z_a), (x_b, y_b, z_b))
ROAD_REGION = BlockRegion.from_xyz_pair((-80, 65, 16), (-17, 75, 127))
ROAD_BOX = _env_block_region("ROAD_BOX", ROAD_REGION)

# Built assets region in world (type, (x_a, y_a, z_a), (x_b, y_b, z_b))
# y0/y1 is retained as catalog metadata; marker blocks define extracted geometry.
BUILD_TYPE1_REGION = BuildRegion(1, BlockRegion.from_xyz_pair((-320, 64, -176), (-17, 65, -17)))
BUILD_TYPE2_REGION = BuildRegion(2, BlockRegion.from_xyz_pair((16, 64, -304), (287, 65, 191)))

BUILD_MARKER_Y_RANGE = VerticalRange(60, 230)
BUILD_TYPES = _env_build_regions("BUILD_TYPES", (BUILD_TYPE1_REGION, BUILD_TYPE2_REGION))
