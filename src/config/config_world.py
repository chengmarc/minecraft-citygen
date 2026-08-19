"""World paths, extraction regions, and schematic version settings."""

import ast
import os

from config.config_path import DEFAULT_WORLD
from config.models import BlockRegion, BuildRegion, VerticalRange
from config.path_discovery import region_dir_candidates, resolve_region_dir


def _parse_python_tuple(value):
    parsed = ast.literal_eval(value)
    if isinstance(parsed, tuple):
        return parsed
    if isinstance(parsed, list):
        return tuple(parsed)
    raise ValueError(f"expected a tuple-like region value, got {type(parsed).__name__}")


def _parse_build_types(value):
    return tuple(BuildRegion.from_values(_parse_python_tuple(item)) for item in value.split(";") if item.strip())


def _parse_block_region(value):
    return BlockRegion.from_values(_parse_python_tuple(value))

# Minecraft world save folder. Override with MC_CITY_SAVE when needed.
SAVE = os.environ.get("MC_CITY_SAVE") or DEFAULT_WORLD
REGION_DIR_CANDIDATES = tuple(region_dir_candidates(SAVE))
REGION_DIR = resolve_region_dir(SAVE)

DATA_VERSION = 4790

# Road assets region in world ((x_a, y_a, z_a), (x_b, y_b, z_b))
ROAD_REGION = BlockRegion.from_xyz_pair((0, 65, 0), (-100, 75, 150))
ROAD_BOX = (
    _parse_block_region(os.environ["MC_CITY_ROAD_BOX"])
    if "MC_CITY_ROAD_BOX" in os.environ
    else ROAD_REGION
)

# Built assets region in world (type, (x_a, y_a, z_a), (x_b, y_b, z_b))
# y0/y1 is retained as catalog metadata; marker blocks define extracted geometry.

BUILD_TYPE1_REGION = BuildRegion(1, BlockRegion.from_xyz_pair((0, 64, 0), (-300, 65, -300)))
BUILD_TYPE2_REGION = BuildRegion(2, BlockRegion.from_xyz_pair((0, 64, 0), (300, 65, -300)))

BUILD_MARKER_Y_RANGE = VerticalRange(60, 230)
BUILD_TYPES = (
    _parse_build_types(os.environ["MC_CITY_BUILD_TYPES"])
    if "MC_CITY_BUILD_TYPES" in os.environ
    else (BUILD_TYPE1_REGION, BUILD_TYPE2_REGION)
)
