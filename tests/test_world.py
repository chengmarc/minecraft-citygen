"""Source-world reading: the Anvil reader, ground detection, and marker parsing.

Assets are authored on a flat terrain surface; detection recovers that surface Y
(via a column scan, not the paste-stale heightmap) so extraction follows the
ground plane wherever the source world is seated. Grown leaves (persistent=false)
decay after a paste unless a log stays in range, so a stable export rewrites them
to persistent=true.
"""
import os
import tempfile
import unittest
from pathlib import Path

from engine.render.topdown import region_world_bounds
from engine.world.anvil_world_reader import World
from engine.world.marker_extract import (
    extract_cuboid,
    group_marker_cuboids,
    marker_blocks_in_region,
    pair_gold_diamond_markers,
)


# --- Anvil reader ---------------------------------------------------------

class AnvilWorldReaderTests(unittest.TestCase):
    def test_world_reports_checked_region_paths_when_region_dir_is_missing(self):
        with self.assertRaises(FileNotFoundError) as exc_info:
            World(region_dir="C:/missing/world/region", save_path="C:/missing/world")

        message = str(exc_info.exception)
        self.assertIn("Configured save: C:/missing/world", message)
        self.assertIn(os.path.normpath("C:/missing/world/region"), message)

    def _pack_heightmap(self, heights, bits=9):
        per_long = 64 // bits
        longs = [0] * ((256 + per_long - 1) // per_long)
        for index, height in enumerate(heights):
            longs[index // per_long] |= int(height) << ((index % per_long) * bits)
        return longs

    def _heightmap_world(self, heights, palette, indexes=None, key="WORLD_SURFACE"):
        chunk = {
            "yPos": -4,
            "sections": [{"Y": y} for y in range(-4, 20)],
            "Heightmaps": {key: self._pack_heightmap(heights)},
        }
        world = object.__new__(World)
        world.load_chunk = lambda cx, cz: chunk
        world._section = lambda cx, cz, sy: (palette, indexes) if sy == 3 else ([{"Name": "minecraft:air"}], None)
        return world

    def test_heightmap_surface_block_uses_world_min_y_offset(self):
        palette = [{"Name": "minecraft:air"}, {"Name": "minecraft:grass_block"}]
        indexes = [0] * 4096
        indexes[15 * 256] = 1  # raw 128 + min_y -64 - 1 -> y 63, local y 15 in section 3
        world = self._heightmap_world([128] * 256, palette, indexes)

        self.assertEqual(world.heightmap_surface_block(0, 0), ("minecraft:grass_block", 63, None))

    def test_heightmap_surface_blocks_decodes_whole_chunk(self):
        world = self._heightmap_world([128] * 256, [{"Name": "minecraft:grass_block"}])

        entries = world.heightmap_surface_blocks(2, -1)

        self.assertEqual(len(entries), 256)
        self.assertEqual(entries[0], ("minecraft:grass_block", 63))
        self.assertEqual(entries[255], ("minecraft:grass_block", 63))

    def test_heightmap_surface_block_accepts_worldgen_surface_heightmap(self):
        world = self._heightmap_world(
            [128] * 256,
            [{"Name": "minecraft:grass_block"}],
            key="WORLD_SURFACE_WG",
        )

        self.assertEqual(world.heightmap_surface_block(0, 0), ("minecraft:grass_block", 63, None))

    def test_heightmap_surface_readers_return_none_when_surface_data_is_unavailable(self):
        chunk = {"yPos": -4, "sections": [{"Y": y} for y in range(-4, 20)]}
        world = object.__new__(World)
        world.load_chunk = lambda cx, cz: chunk

        self.assertIsNone(world.heightmap_surface_block(0, 0))
        self.assertEqual(world.heightmap_surface_blocks(0, 0), [None] * 256)

        absent_world = object.__new__(World)
        absent_world.load_chunk = lambda cx, cz: None

        self.assertIsNone(absent_world.heightmap_surface_block(0, 0))

    def test_block_positions_in_section_returns_target_world_coordinates(self):
        palette = [
            {"Name": "minecraft:air"},
            {"Name": "minecraft:gold_block"},
            {"Name": "minecraft:emerald_block"},
        ]
        indexes = [0] * 4096
        indexes[2 * 256 + 3 * 16 + 4] = 1
        indexes[5 * 256 + 6 * 16 + 7] = 2
        world = object.__new__(World)
        world.load_chunk = lambda cx, cz: {
            "sections": [
                {
                    "Y": 4,
                    "block_states": {
                        "palette": palette,
                        "data": [0],
                    },
                }
            ]
        }
        world._section = lambda cx, cz, sy: (palette, indexes)

        self.assertEqual(
            world.block_positions_in_section(2, -1, 4, {"minecraft:gold_block", "minecraft:emerald_block"}),
            [
                (36, 66, -13, "minecraft:gold_block"),
                (39, 69, -10, "minecraft:emerald_block"),
            ],
        )


def test_gold_markers_pair_with_closest_unused_diamonds():
    golds = [(10, 64, 10), (100, 64, 10)]
    diamonds = [(6, 70, 6), (90, 80, 2)]
    cuboids, skipped = pair_gold_diamond_markers(golds, diamonds)

    assert skipped == []
    assert cuboids == [
        ((6, 10, 64, 70, 6, 10), (10, 64, 10)),
        ((90, 100, 64, 80, 2, 10), (100, 64, 10)),
    ]


def test_gold_markers_ignore_diamonds_outside_north_west_up_direction():
    cuboids, skipped = pair_gold_diamond_markers(
        golds=[(10, 64, 10)],
        diamonds=[(9, 63, 9), (11, 70, 9), (9, 70, 11)],
    )

    assert cuboids == []
    assert skipped == [
        (10, 10, "no north/west/up diamond marker available for gold (10, 64, 10)"),
        (9, 9, "unused diamond marker (9, 63, 9)"),
        (11, 9, "unused diamond marker (11, 70, 9)"),
        (9, 11, "unused diamond marker (9, 70, 11)"),
    ]


def test_build_cuboids_group_by_vertical_alignment():
    cuboids = [
        ((0, 8, 80, 89, 0, 8), (8, 80, 8)),
        ((20, 28, 70, 75, 0, 8), (28, 70, 8)),
        ((0, 8, 64, 69, 0, 8), (8, 64, 8)),
        ((0, 8, 70, 79, 0, 8), (8, 70, 8)),
    ]

    components, skipped = group_marker_cuboids(cuboids, emeralds=[(9, 63, 9), (29, 70, 9)])

    assert skipped == []
    assert len(components) == 2
    assert components[0].cuboids == [
        (0, 8, 64, 69, 0, 8),
        (0, 8, 70, 79, 0, 8),
        (0, 8, 80, 89, 0, 8),
    ]
    assert components[0].ground_offset == -1
    assert components[1].cuboids == [(20, 28, 70, 75, 0, 8)]


def test_build_cuboids_skip_invalid_layer_counts():
    components, skipped = group_marker_cuboids([
        ((0, 8, 64, 69, 0, 8), (8, 64, 8)),
        ((0, 8, 70, 79, 0, 8), (8, 70, 8)),
    ], emeralds=[(9, 64, 9)])

    assert components == []
    assert skipped == [(0, 0, "expected 1 or 3 vertically aligned layer(s), got 2")]


def test_build_cuboids_require_emerald_adjacent_to_bottom_gold():
    components, skipped = group_marker_cuboids([
        ((0, 8, 64, 69, 0, 8), (8, 64, 8)),
    ], emeralds=[(10, 64, 10)])

    assert components == []
    assert skipped == [(0, 0, "no horizontally adjacent emerald marker for gold (8, 64, 8)")]


class _SectionMarkerWorld:
    def __init__(self, markers_by_section):
        self.markers_by_section = markers_by_section

    def is_chunk_empty(self, cx, cz):
        return False

    def block_positions_in_section(self, cx, cz, sy, block_names):
        return self.markers_by_section.get((cx, cz, sy), [])


def test_marker_blocks_in_region_clips_section_results_to_selected_bounds():
    world = _SectionMarkerWorld({
        (0, 0, 4): [
            (1, 64, 2, "minecraft:gold_block"),
            (20, 64, 2, "minecraft:diamond_block"),  # outside X bounds
            (3, 80, 4, "minecraft:emerald_block"),   # outside Y bounds
            (4, 65, 20, "minecraft:emerald_block"),  # outside Z bounds
        ]
    })
    markers = marker_blocks_in_region(
        world, 0, 15, 0, 15, (64, 79),
    )

    assert markers == {
        "gold_block": [(1, 64, 2)],
        "diamond_block": [],
        "emerald_block": [],
    }


# --- marker parsing: cuboid leaf persistence ------------------------------

class _FixedBlockWorld:
    """Returns a fixed (name, props) for every column, ignoring coordinates."""

    def __init__(self, name, props):
        self._name = name
        self._props = props

    def block(self, x, y, z):
        return self._name, (dict(self._props) if self._props else None)

    def load_chunk(self, cx, cz):
        return None  # no block entities in this fake


def _single(world, *, force):
    # A 1x1x1 cuboid -> cells[0][0][0] is the one block state string.
    cells, _block_entities = extract_cuboid(world, (0, 0, 0, 0, 0, 0), force_persistent_leaves=force)
    return cells[0][0][0]


def test_grown_leaves_forced_persistent():
    world = _FixedBlockWorld("minecraft:cherry_leaves", {"distance": "7", "persistent": "false"})
    assert _single(world, force=True) == "minecraft:cherry_leaves[distance=7,persistent=true]"


def test_grown_leaves_untouched_when_disabled():
    world = _FixedBlockWorld("minecraft:cherry_leaves", {"distance": "7", "persistent": "false"})
    assert _single(world, force=False) == "minecraft:cherry_leaves[distance=7,persistent=false]"


# --- world preview bounds -------------------------------------------------

class WorldPreviewTests(unittest.TestCase):
    def test_region_world_bounds_uses_region_file_coordinates(self):
        with tempfile.TemporaryDirectory() as tempdir:
            region_dir = Path(tempdir)
            for name in ("r.-1.-1.mca", "r.-1.0.mca", "r.0.-1.mca"):
                (region_dir / name).write_bytes(b"")

            self.assertEqual(region_world_bounds(region_dir), (-512, 511, -512, 511))


if __name__ == "__main__":
    unittest.main()
