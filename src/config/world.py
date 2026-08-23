"""World paths, extraction regions, and schematic version settings."""

from __future__ import annotations

import ast

from config.path import DEFAULT_WORLD
from config.path import env_raw, env_str
from config.models import BlockRegion, BuildRegion, VerticalRange
from config.path import region_dir_candidates, resolve_region_dir
from config.version_compat import HARD_FLOOR_DATA_VERSION, detect_world_data_version


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

# Schematic DataVersion (the version WorldEdit assumes when pasting). Forward-only
# compatibility: this is always the source world's own version, so WorldEdit's
# DataFixer upgrades the schematic forward on paste. Resolves to the GUI-pinned
# MC_CITY_DATA_VERSION (the source version, set explicitly because construct/render
# do not set MC_CITY_SAVE), else the source world's detected version, else the
# hard floor; always clamped up to the hard floor. See config/version_compat.py.
def _resolve_data_version() -> int:
    raw = env_raw("DATA_VERSION")
    if raw is not None:
        return max(int(raw.strip()), HARD_FLOOR_DATA_VERSION)
    detected = detect_world_data_version(SAVE)
    resolved = detected if detected is not None else HARD_FLOOR_DATA_VERSION
    return max(resolved, HARD_FLOOR_DATA_VERSION)


DATA_VERSION = _resolve_data_version()

# Road assets region in world ((x_a, y_a, z_a), (x_b, y_b, z_b))
ROAD_REGION = BlockRegion.from_xyz_pair((-80, 65, -256), (-17, 75, -145))
ROAD_BOX = _env_block_region("ROAD_BOX", ROAD_REGION)

# Built assets region in world (type, (x_a, y_a, z_a), (x_b, y_b, z_b))
# y0/y1 is retained as catalog metadata; marker blocks define extracted geometry.

BUILD_TYPE1_REGION = BuildRegion(1, BlockRegion.from_xyz_pair((-272, 64, -144), (-1, 65, -1)))
BUILD_TYPE2_REGION = BuildRegion(2, BlockRegion.from_xyz_pair((0, 64, -256), (383, 65, -1)))

BUILD_MARKER_Y_RANGE = VerticalRange(60, 230)
BUILD_TYPES = _env_build_regions("BUILD_TYPES", (BUILD_TYPE1_REGION, BUILD_TYPE2_REGION))

# Source-world ground plane (grass level) the extraction Y windows above are
# authored against. Each stage detects the actual source ground at run time and
# shifts its wool/marker search windows by the difference, so a source world
# seated at any Y works. Distinct from the emerald marker's per-asset ground_y
# and the generated city_ground_y. See engine/marker_extract.detect_source_ground_y.
REFERENCE_GROUND_Y = 63
