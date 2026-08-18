"""World paths, extraction regions, and schematic version settings."""

import os


def _parse_int_tuple(value, expected_len):
    parts = [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    if len(parts) != expected_len:
        raise ValueError(f"expected {expected_len} values, got {len(parts)}")
    return tuple(int(part) for part in parts)


def _parse_build_types(value):
    return [_parse_int_tuple(item, 7) for item in value.split(";") if item.strip()]

# Minecraft world (PrismLauncher save)
SAVE = os.environ.get(
    "MC_CITY_SAVE",
    (r"C:/Users/NewAdmin/AppData/Roaming/PrismLauncher/instances/"
     r"Keo optimized/minecraft/saves/Flat 64 2.0"),
)
REGION_DIR = SAVE + "/dimensions/minecraft/overworld/region"

DATA_VERSION = 4790

# Road assets region in world (x_a, x_b, z_a, z_b, y0, y1)
ROAD_MODERN = (-230, -176, 16, 121, 65, 75)
ROAD_MEDIEVAL = (-294, -240, 16, 121, 65, 75)
ROAD_BOX = (
    _parse_int_tuple(os.environ["MC_CITY_ROAD_BOX"], 6)
    if "MC_CITY_ROAD_BOX" in os.environ
    else ROAD_MODERN
)

# Built assets region in world (type, x_a, x_b, z_a, z_b, y0, y1)
# y0/y1 is retained as catalog metadata; marker blocks define extracted geometry.

BUILD_MEDIEVAL = (1, 0, -366, -266, -140, 64, 65) 
BUILD_MODERN_A = (1, 0, -366, 0, -135, 64, 65)
BUILD_MODERN_B = (1, 0, -234, -267, -383, 64, 65)
BUILD_MODERN_TYPE2 = (2, 0, 300, 0, -300, 64, 65)

BUILD_MARKER_Y_RANGE = (60, 230)
BUILD_TYPES = (
    _parse_build_types(os.environ["MC_CITY_BUILD_TYPES"])
    if "MC_CITY_BUILD_TYPES" in os.environ
    else [BUILD_MODERN_A, BUILD_MODERN_TYPE2]
)
