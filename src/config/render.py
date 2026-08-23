"""Rendering and preview style constants for generated artifacts."""

from __future__ import annotations

ROAD_ASSET_ISO_TILE_W = 12
ROAD_ASSET_ISO_TILE_H = 6
ROAD_ASSET_ISO_BLOCK_H = 8

FULL_SCHEM_ISO_TILE_W = 4
FULL_SCHEM_ISO_TILE_H = 2
FULL_SCHEM_ISO_BLOCK_H = 3

ISO_MARGIN = 16
CONTACT_SHEET_BG = (30, 30, 34, 255)
UNKNOWN_BLOCK_RGBA = (255, 0, 255)

CITY_GROUND_FILL_BLOCK = "minecraft:smooth_stone_slab[type=bottom]"
CITY_GROUND_FILL_RGBA = (159, 159, 159, 255)
CITY_ANCHOR_BLOCK = "minecraft:smooth_stone"   # solid block for the origin anchor column
CITY_GROUND_Y = 1

BUILD_PREVIEW_COLORS = {
    1: {
        "wall": (185, 156, 108),
        "roof": (126, 65, 48),
        "roof_alt": (156, 88, 58),
        "line": (92, 55, 42),
        "front": (47, 39, 34),
        "glass": (93, 130, 150),
    },
    2: {
        "wall": (150, 158, 166),
        "roof": (76, 86, 96),
        "roof_alt": (102, 115, 126),
        "line": (45, 53, 62),
        "front": (30, 34, 39),
        "glass": (84, 152, 178),
    },
}
