import os
import unittest

from engine.anvil_world_reader import World


class AnvilWorldReaderTests(unittest.TestCase):
    def test_world_reports_checked_region_paths_when_region_dir_is_missing(self):
        with self.assertRaises(FileNotFoundError) as exc_info:
            World(
                region_dir="C:/missing/world/region",
                save_path="C:/missing/world",
            )

        message = str(exc_info.exception)
        self.assertIn("Configured save: C:/missing/world", message)
        self.assertIn(os.path.normpath("C:/missing/world/region"), message)


class TopSolidBlockTests(unittest.TestCase):
    def _world(self, sections, section_ys):
        """Build a World bypassing __init__, with mocked chunk/section access."""
        world = object.__new__(World)
        world.load_chunk = lambda cx, cz: {"sections": [{"Y": y} for y in section_ys]}
        world._section = lambda cx, cz, sy: sections[sy]
        return world

    def test_returns_highest_non_air_block_skipping_air_above(self):
        air = ([{"Name": "minecraft:air"}], None)  # uniform air section
        leaf_palette = [{"Name": "minecraft:air"}, {"Name": "minecraft:oak_leaves"}]
        leaf_idx = [0] * 4096
        leaf_idx[2 * 256] = 1  # (x=0, z=0) at local y=2 -> world y = (4<<4)+2 = 66
        sections = {5: air, 4: (leaf_palette, leaf_idx), 3: ([{"Name": "minecraft:stone"}], None)}
        world = self._world(sections, section_ys=[3, 4, 5])

        self.assertEqual(world.top_solid_block(0, 0), ("minecraft:oak_leaves", 66, None))

    def test_falls_through_to_lower_section_when_upper_is_air(self):
        air = ([{"Name": "minecraft:air"}], None)
        sections = {5: air, 4: air, 3: ([{"Name": "minecraft:stone"}], None)}
        world = self._world(sections, section_ys=[3, 4, 5])

        name, y, _props = world.top_solid_block(0, 0)
        self.assertEqual(name, "minecraft:stone")
        self.assertEqual(y, (3 << 4) + 15)  # top of the stone section

    def test_returns_none_for_absent_chunk(self):
        world = object.__new__(World)
        world.load_chunk = lambda cx, cz: None
        self.assertIsNone(world.top_solid_block(0, 0))


class SurfaceHeightmapTests(unittest.TestCase):
    def _packed_chunk(self, column_values, section_ys):
        # WORLD_SURFACE packs 256 values into longs, 7 per long at 9 bits.
        n_longs = -(-256 // 7)
        longs = [0] * n_longs
        for i, value in enumerate(column_values):
            long_index, offset = divmod(i, 7)
            longs[long_index] |= (value & 0x1FF) << (offset * 9)
        return {
            "Heightmaps": {"WORLD_SURFACE": longs},
            "sections": [{"Y": y} for y in section_ys],
        }

    def test_decodes_world_surface_heights(self):
        min_y = -64  # section Ys -4..19

        def stored(surface_y):
            return surface_y - min_y + 1  # heightmap stores blocks-above-bottom

        values = [0] * 256
        values[0] = stored(70)
        values[8] = stored(-10)  # spills into the second long (index 8 -> long 1)
        chunk = self._packed_chunk(values, section_ys=range(-4, 20))

        world = object.__new__(World)
        world.load_chunk = lambda cx, cz: chunk

        heights, got_min_y = world.surface_heightmap(0, 0)
        self.assertEqual(got_min_y, min_y)
        self.assertEqual(heights[0], 70)
        self.assertEqual(heights[8], -10)
        self.assertIsNone(heights[1])  # stored value 0 -> empty column

    def test_returns_none_when_heightmap_absent(self):
        world = object.__new__(World)
        world.load_chunk = lambda cx, cz: {"sections": [{"Y": 0}]}
        self.assertEqual(world.surface_heightmap(0, 0), (None, 0))


if __name__ == "__main__":
    unittest.main()
