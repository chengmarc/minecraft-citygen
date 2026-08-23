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
    detect_source_ground_y,
    extract_cuboid,
    ground_shift,
    sign_text,
)


# --- Anvil reader ---------------------------------------------------------

class AnvilWorldReaderTests(unittest.TestCase):
    def test_world_reports_checked_region_paths_when_region_dir_is_missing(self):
        with self.assertRaises(FileNotFoundError) as exc_info:
            World(region_dir="C:/missing/world/region", save_path="C:/missing/world")

        message = str(exc_info.exception)
        self.assertIn("Configured save: C:/missing/world", message)
        self.assertIn(os.path.normpath("C:/missing/world/region"), message)

    def _world(self, sections, section_ys):
        """Build a World bypassing __init__, with mocked chunk/section access."""
        world = object.__new__(World)
        world.load_chunk = lambda cx, cz: {"sections": [{"Y": y} for y in section_ys]}
        world._section = lambda cx, cz, sy: sections[sy]
        return world

    def test_top_solid_block_returns_highest_non_air_skipping_air_above(self):
        air = ([{"Name": "minecraft:air"}], None)  # uniform air section
        leaf_palette = [{"Name": "minecraft:air"}, {"Name": "minecraft:oak_leaves"}]
        leaf_idx = [0] * 4096
        leaf_idx[2 * 256] = 1  # (x=0, z=0) at local y=2 -> world y = (4<<4)+2 = 66
        sections = {5: air, 4: (leaf_palette, leaf_idx), 3: ([{"Name": "minecraft:stone"}], None)}
        world = self._world(sections, section_ys=[3, 4, 5])

        self.assertEqual(world.top_solid_block(0, 0), ("minecraft:oak_leaves", 66, None))

    def test_top_solid_block_returns_none_for_absent_chunk(self):
        world = object.__new__(World)
        world.load_chunk = lambda cx, cz: None
        self.assertIsNone(world.top_solid_block(0, 0))


# --- ground detection -----------------------------------------------------

def _chunk_tops(surface_y):
    """Build a 256-entry top_solid_blocks array from a ``(x, z) -> y`` callable.

    Columns are indexed ``z_local * 16 + x_local`` and world coords are the
    caller's absolute block positions -- matching the real World API.
    """
    def blocks(cx, cz):
        entries = []
        for col in range(256):
            x = (cx << 4) + (col & 15)
            z = (cz << 4) + (col >> 4)
            entries.append(("minecraft:grass_block", surface_y(x, z)))
        return entries
    return blocks


class _FlatGroundWorld:
    """Flat ground at ``ground_y``; a sparse grid of columns raised (builds)."""

    def __init__(self, ground_y, empty=False):
        self.ground_y = ground_y
        self.empty = empty

    def is_chunk_empty(self, cx, cz):
        return self.empty

    def top_solid_blocks(self, cx, cz):
        raised = lambda x, z: self.ground_y + (8 if (x % 20 == 0 and z % 20 == 0) else 0)
        return _chunk_tops(raised)(cx, cz)


class _RoadDenseWorld:
    """Most columns at a raised road surface; grass ground exposed in a minority."""

    def __init__(self, ground_y, road_y):
        self.ground_y = ground_y
        self.road_y = road_y

    def is_chunk_empty(self, cx, cz):
        return False

    def top_solid_blocks(self, cx, cz):
        # ~1/3 of columns show bare ground, the rest the higher road surface.
        surface = lambda x, z: self.ground_y if (x + z) % 3 == 0 else self.road_y
        return _chunk_tops(surface)(cx, cz)


def test_detects_ground_plane():
    # Ground dominates; the sparse raised columns must not sway detection.
    assert detect_source_ground_y(_FlatGroundWorld(-61), -272, 47, -272, 47) == -61
    assert detect_source_ground_y(_FlatGroundWorld(63), -80, -17, -256, -145) == 63


def test_ground_is_lowest_common_surface_not_the_mode():
    # The road surface (-58) is the *most common* level, but ground is -61; the
    # detector must return the lower broadly-present plane, not the mode.
    assert detect_source_ground_y(_RoadDenseWorld(-61, -58), -80, -17, -256, -145) == -61


def test_ground_shift_is_delta_from_reference():
    # New 1.19.4 world (ground -61) against the config reference (63) -> -124.
    assert ground_shift(_FlatGroundWorld(-61), -80, -17, -256, -145, 63) == -124
    # A world already at the reference needs no shift.
    assert ground_shift(_FlatGroundWorld(63), -80, -17, -256, -145, 63) == 0


def test_ground_shift_zero_when_undetectable():
    # Undetectable ground (empty region) preserves the configured absolute windows.
    assert ground_shift(_FlatGroundWorld(0, empty=True), 0, 15, 0, 15, 63) == 0


# --- marker parsing: signs ------------------------------------------------

def test_sign_text_reads_legacy_text1_4():
    be = {
        "Text1": '{"text":"01_big"}',
        "Text2": '{"text":"_2x2"}',
        "Text3": '{"text":"_deadend"}',
        "Text4": '{"text":""}',
    }
    assert sign_text(be) == "01_big _2x2 _deadend"


def test_sign_text_reads_modern_front_back_text():
    be = {"front_text": {"messages": ["stack: 5-7", "", "appearance: 4-6", ""]}}
    assert sign_text(be) == "stack: 5-7 appearance: 4-6"


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
