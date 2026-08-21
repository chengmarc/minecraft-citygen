"""World paths, extraction regions, and schematic version settings."""

from __future__ import annotations

import ast
import os

from config.config_path import DEFAULT_WORLD
from config.models import BlockRegion, BuildRegion, VerticalRange
from config.path_discovery import region_dir_candidates, resolve_region_dir
from config.version_compat import (
    FALLBACK_DATA_VERSION,
    SUPPORTED_FLOOR,
    detect_world_data_version,
)


def _parse_tuple_like(value: str):
    parsed = ast.literal_eval(value)
    if isinstance(parsed, tuple):
        return parsed
    if isinstance(parsed, list):
        return tuple(parsed)
    raise ValueError(f"expected a tuple-like region value, got {type(parsed).__name__}")


def _env_value(name: str, default: str) -> str:
    return os.environ.get(name) or default


def _parse_build_types(value: str) -> tuple[BuildRegion, ...]:
    return tuple(BuildRegion.from_values(_parse_tuple_like(item)) for item in value.split(";") if item.strip())


def _parse_block_region(value: str) -> BlockRegion:
    return BlockRegion.from_values(_parse_tuple_like(value))


def _env_block_region(name: str, default: BlockRegion) -> BlockRegion:
    raw = os.environ.get(name)
    return default if raw is None else _parse_block_region(raw)


def _env_build_regions(name: str, default: tuple[BuildRegion, ...]) -> tuple[BuildRegion, ...]:
    raw = os.environ.get(name)
    return default if raw is None else _parse_build_types(raw)

# Minecraft world save folder. Override with MC_CITY_SAVE when needed.
SAVE = _env_value("MC_CITY_SAVE", DEFAULT_WORLD)
REGION_DIR_CANDIDATES = tuple(region_dir_candidates(SAVE))
REGION_DIR = resolve_region_dir(SAVE)

# Schematic DataVersion (the version WorldEdit assumes when pasting). Resolves
# to the explicit target override, else the source world's own version, else a
# sane fallback, clamped up to the hard floor. See config/version_compat.py.
def _resolve_data_version() -> int:
    raw = os.environ.get("MC_CITY_DATA_VERSION")
    if raw and raw.strip():
        return max(int(raw.strip()), SUPPORTED_FLOOR)
    detected = detect_world_data_version(SAVE)
    resolved = detected if detected is not None else FALLBACK_DATA_VERSION
    return max(resolved, SUPPORTED_FLOOR)


DATA_VERSION = _resolve_data_version()

# Road assets region in world ((x_a, y_a, z_a), (x_b, y_b, z_b))
ROAD_REGION = BlockRegion.from_xyz_pair((-80, 65, -256), (-17, 75, -145))
ROAD_BOX = _env_block_region("MC_CITY_ROAD_BOX", ROAD_REGION)

# Built assets region in world (type, (x_a, y_a, z_a), (x_b, y_b, z_b))
# y0/y1 is retained as catalog metadata; marker blocks define extracted geometry.

BUILD_TYPE1_REGION = BuildRegion(1, BlockRegion.from_xyz_pair((-272, 64, -144), (-1, 65, -1)))
BUILD_TYPE2_REGION = BuildRegion(2, BlockRegion.from_xyz_pair((0, 64, -256), (383, 65, -1)))

BUILD_MARKER_Y_RANGE = VerticalRange(60, 230)
BUILD_TYPES = _env_build_regions("MC_CITY_BUILD_TYPES", (BUILD_TYPE1_REGION, BUILD_TYPE2_REGION))
