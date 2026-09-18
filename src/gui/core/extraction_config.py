"""Extraction settings: source world, asset regions, and the version stamp."""

from __future__ import annotations

from config.world import (
    BUILD_TYPES, RELEASE_NAMES, ROAD_BOX, SAVE,
    BlockRegion, BuildRegion,
)


# Sentinel meaning "no explicit paste target chosen" in the selector.
AUTO_VERSION = "auto"


def region_to_xyz_pair(region):
    if isinstance(region, BuildRegion):
        return region.bounds.as_xyz_pair()
    if isinstance(region, BlockRegion):
        return region.as_xyz_pair()
    raise TypeError(f"Unsupported region type: {type(region).__name__}")


def first_build_region(build_types, build_type):
    for region in build_types:
        if region.build_type == build_type:
            return region
    return BuildRegion(build_type, BlockRegion(0, 0, 0, 0, 64, 64))


def _serialize_xyz_pair(start, end):
    return {
        "start": list(start),
        "end": list(end),
    }


def default_extraction_tab_config():
    road_start, road_end = region_to_xyz_pair(ROAD_BOX)
    house_start, house_end = region_to_xyz_pair(first_build_region(BUILD_TYPES, 1))
    landmark_start, landmark_end = region_to_xyz_pair(first_build_region(BUILD_TYPES, 2))
    return {
        "world_path": SAVE,
        "target_version": AUTO_VERSION,
        "road": _serialize_xyz_pair(road_start, road_end),
        "house": _serialize_xyz_pair(house_start, house_end),
        "landmark": _serialize_xyz_pair(landmark_start, landmark_end),
    }


def version_selector_items(min_data_version=None):
    """(label, value) pairs for the paste-target dropdown, newest first.

    Indicator only: it lists the Minecraft versions the output can be pasted into
    -- the source version and newer -- so the user can confirm the target. It
    does not affect the stamp, which is always the source version (see
    config.world.source_data_version). When min_data_version is given, only versions at
    or above it are listed.
    """
    items = [("Auto", AUTO_VERSION)]
    items.extend(
        (name, name)
        for dv, name in sorted(RELEASE_NAMES.items(), reverse=True)
        if min_data_version is None or dv >= min_data_version
    )
    return items
