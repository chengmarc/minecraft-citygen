"""World export: the schem -> standalone copied-world writer.

The writer is the inverse of the Anvil reader, so the strongest check is a
round trip: write a grid out as a world, read it back with ``World``, and assert
every block (and its properties, block entities, and the level.dat spawn) survived.
"""
import os
import tempfile
import unittest

import numpy as np
import nbtlib
from nbtlib import Byte, Compound, String

from config.path import resolve_region_dir
from engine.schematic.transform import BlockEntity
from engine.schematic.writer import write_sponge_schem_grid
from engine.world.anvil_world_reader import World
from engine.world import writer as world_writer

STONE = "minecraft:stone"
STAIRS = "minecraft:oak_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]"
SIGN = "minecraft:oak_sign[rotation=0,waterlogged=false]"
DATA_VERSION = 3463  # 1.20.1


def _sample_grid():
    """A small city-like grid: a full stone ground plane plus a stair and a sign.

    Shape is (H, L, W) indexed [y][z][x]; L/W = 18 so it spans two chunks on each
    axis. Returns (grid_indices, inv, block_entities).
    """
    inv = {0: "minecraft:air", 1: STONE, 2: STAIRS, 3: SIGN}
    grid = np.zeros((20, 18, 18), dtype=np.int16)
    grid[0, :, :] = 1                 # ground plane so every column is solid
    grid[1, 5, 5] = 2                 # a block carrying properties
    grid[1, 8, 8] = 3                 # a sign (has a block entity)
    block_entities = [
        BlockEntity(8, 1, 8, "minecraft:oak_sign", Compound({
            "is_waxed": Byte(0),
            "front_text": Compound({"messages": nbtlib.List[String]([String("hello")])}),
        }))
    ]
    return grid, inv, block_entities


class WorldWriterRoundTripTests(unittest.TestCase):
    def test_every_block_survives_the_round_trip(self):
        grid, inv, block_entities = _sample_grid()
        base_y = 64
        with tempfile.TemporaryDirectory() as out:
            world_writer.write_world(
                grid, inv, block_entities, out, DATA_VERSION, base_y, origin=(0, 0)
            )
            world = World(region_dir=resolve_region_dir(out), save_path=out)

            h, length, width = grid.shape
            for y in range(h):
                for z in range(length):
                    for x in range(width):
                        state = inv[int(grid[y, z, x])]
                        name, props = world_writer.parse_state(state)
                        read_name, read_props = world.block(x, y + base_y, z)
                        if name == "minecraft:air":
                            self.assertIn(read_name, world_writer.AIR_NAMES)
                        else:
                            self.assertEqual((read_name, read_props or None), (name, props or None))

    def test_block_entity_survives_with_absolute_coords(self):
        grid, inv, block_entities = _sample_grid()
        base_y = 64
        with tempfile.TemporaryDirectory() as out:
            world_writer.write_world(
                grid, inv, block_entities, out, DATA_VERSION, base_y, origin=(0, 0)
            )
            world = World(region_dir=resolve_region_dir(out), save_path=out)
            chunk = world.load_chunk(0, 0)  # sign at world (8, 65, 8) -> chunk (0, 0)
            entries = [be for be in chunk["block_entities"]
                       if (int(be["x"]), int(be["y"]), int(be["z"])) == (8, 65, 8)]
            self.assertEqual(len(entries), 1)
            self.assertEqual(str(entries[0]["id"]), "minecraft:oak_sign")
            self.assertEqual(int(entries[0]["is_waxed"]), 0)


class SchemToWorldTests(unittest.TestCase):
    def _write_schem(self, path):
        # offset y = -(city_ground_y + 1); city_ground_y = 0 -> ground seats at y=64.
        grid, inv, block_entities = _sample_grid()
        palette = {state: idx for idx, state in inv.items()}
        write_sponge_schem_grid(
            grid, palette, path, DATA_VERSION,
            offset=(0, -1, 0), block_entities=block_entities,
        )

    def test_exported_world_and_spawn_stands_on_solid_ground(self):
        with tempfile.TemporaryDirectory() as tmp:
            schem = os.path.join(tmp, "city.schem")
            out = os.path.join(tmp, "world")
            self._write_schem(schem)

            summary = world_writer.schem_to_world(schem, out)
            self.assertGreater(summary["chunks"], 0)

            data = nbtlib.load(os.path.join(out, "level.dat"))["Data"]
            # World version matches the schematic's own stamp, not the ambient env.
            self.assertEqual(int(data["DataVersion"]), DATA_VERSION)
            self.assertEqual(str(data["LevelName"]), "CityGen World")

            # The saved player sits one block above a solid column (no void drop).
            px, py, pz = (float(v) for v in data["Player"]["Pos"])
            world = World(region_dir=resolve_region_dir(out), save_path=out)
            self.assertNotIn(world.block(int(px), int(py) - 1, int(pz))[0], world_writer.AIR_NAMES)

            # The app icon is written as the 64x64 world icon for the save list.
            from PIL import Image
            icon = os.path.join(out, "icon.png")
            self.assertTrue(os.path.exists(icon))
            with Image.open(icon) as im:
                self.assertEqual(im.size, (64, 64))

    def _fake_source_world(self, tmp, data_version, *, nested_overworld=False, include_player=True):
        """A source world dir whose save layout and ``level.dat`` are native."""
        source = os.path.join(tmp, "source")
        region_dir = (
            os.path.join(source, "dimensions", "minecraft", "overworld", "region")
            if nested_overworld
            else os.path.join(source, "region")
        )
        os.makedirs(region_dir, exist_ok=True)
        with open(os.path.join(region_dir, "r.99.99.mca"), "wb") as fh:
            fh.write(b"stale region")
        with open(os.path.join(region_dir, "keep.txt"), "w", encoding="utf-8") as fh:
            fh.write("keep me")
        os.makedirs(os.path.join(source, "data"), exist_ok=True)
        with open(os.path.join(source, "data", "marker.txt"), "w", encoding="utf-8") as fh:
            fh.write("copied")

        data = Compound({
            "DataVersion": nbtlib.Int(data_version),
            "Version": Compound({"Id": nbtlib.Int(data_version), "Name": String("26.1.2"), "Series": String("main")}),
            "DataPacks": Compound({"Enabled": nbtlib.List[String]([String("vanilla"), String("myworldpack")]),
                                   "Disabled": nbtlib.List[String]([])}),
            "WorldGenSettings": Compound({
                "seed": nbtlib.Long(12345),
                "dimensions": Compound({
                    "minecraft:overworld": Compound({
                        "type": String("minecraft:overworld"),
                        "generator": Compound({"type": String("minecraft:noise"), "settings": String("minecraft:overworld")}),
                    }),
                    "minecraft:the_nether": Compound({"type": String("minecraft:the_nether"), "generator": Compound({})}),
                }),
            }),
        })
        if include_player:
            data["Player"] = Compound({
                "Pos": nbtlib.List[nbtlib.Double]([nbtlib.Double(10.5), nbtlib.Double(80.0), nbtlib.Double(-12.5)]),
                "Dimension": String("minecraft:the_nether"),
                "SeenCredits": Byte(1),
            })
        level = nbtlib.File({"Data": data})
        level.gzipped = True
        level.save(os.path.join(source, "level.dat"))
        return source

    def test_uses_source_level_dat_kept_native_and_recenters_player(self):
        # The export keeps the source world's native version and worldgen, and only
        # changes the copied save's name plus player/spawn location.
        with tempfile.TemporaryDirectory() as tmp:
            source = self._fake_source_world(tmp, 4790)  # 26.1.2
            schem = os.path.join(tmp, "city.schem")
            out = os.path.join(tmp, "world")
            self._write_schem(schem)

            world_writer.schem_to_world(schem, out, source_world=source)

            data = nbtlib.load(os.path.join(out, "level.dat"))["Data"]
            self.assertEqual(int(data["DataVersion"]), 4790)            # native, not floor
            self.assertEqual(int(data["Version"]["Id"]), 4790)
            wgs = data["WorldGenSettings"]
            self.assertEqual(int(wgs["seed"]), 12345)                   # native seed preserved
            self.assertIn("minecraft:the_nether", wgs["dimensions"])    # native dims preserved
            self.assertEqual([str(p) for p in data["DataPacks"]["Enabled"]], ["vanilla", "myworldpack"])
            self.assertEqual(str(data["LevelName"]), "CityGen World")
            gen = wgs["dimensions"]["minecraft:overworld"]["generator"]
            self.assertEqual(str(gen["type"]), "minecraft:noise")       # native worldgen preserved
            self.assertEqual(str(data["Player"]["Dimension"]), "minecraft:overworld")
            self.assertEqual(int(data["Player"]["SeenCredits"]), 1)     # existing player state kept
            self.assertEqual((int(data["SpawnX"]), int(data["SpawnY"]), int(data["SpawnZ"])), (0, 65, 0))
            self.assertTrue(os.path.exists(os.path.join(out, "data", "marker.txt")))

    def test_source_without_player_still_gets_centered_spawn(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self._fake_source_world(tmp, 4790, include_player=False)
            schem = os.path.join(tmp, "city.schem")
            out = os.path.join(tmp, "world")
            self._write_schem(schem)

            world_writer.schem_to_world(schem, out, source_world=source)  # must not raise

            data = nbtlib.load(os.path.join(out, "level.dat"))["Data"]
            self.assertEqual(str(data["LevelName"]), "CityGen World")
            self.assertEqual(str(data["Player"]["Dimension"]), "minecraft:overworld")
            self.assertEqual((int(data["SpawnX"]), int(data["SpawnY"]), int(data["SpawnZ"])), (0, 65, 0))

    def test_export_uses_source_overworld_layout_and_purges_only_region_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self._fake_source_world(tmp, 4790, nested_overworld=True)
            schem = os.path.join(tmp, "city.schem")
            out = os.path.join(tmp, "world")
            self._write_schem(schem)

            world_writer.schem_to_world(schem, out, source_world=source)

            region_dir = resolve_region_dir(out)
            self.assertEqual(region_dir, os.path.join(out, "dimensions", "minecraft", "overworld", "region"))
            self.assertFalse(os.path.exists(os.path.join(region_dir, "r.99.99.mca")))
            self.assertTrue(os.path.exists(os.path.join(region_dir, "keep.txt")))
            self.assertGreater(len([name for name in os.listdir(region_dir) if name.endswith(".mca")]), 0)
            self.assertFalse(os.path.exists(os.path.join(out, "region", "r.0.0.mca")))

    def test_stale_output_dir_is_replaced_before_copying_source_world(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self._fake_source_world(tmp, 4790)
            schem = os.path.join(tmp, "city.schem")
            out = os.path.join(tmp, "world")
            self._write_schem(schem)

            os.makedirs(out)
            with open(os.path.join(out, "stale.txt"), "w", encoding="utf-8") as fh:
                fh.write("junk")

            world_writer.schem_to_world(schem, out, source_world=source)
            self.assertFalse(os.path.exists(os.path.join(out, "stale.txt")))
            self.assertTrue(os.path.exists(os.path.join(out, "data", "marker.txt")))

    def test_invalid_explicit_source_world_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            schem = os.path.join(tmp, "city.schem")
            out = os.path.join(tmp, "world")
            self._write_schem(schem)

            missing = os.path.join(tmp, "missing")
            with self.assertRaisesRegex(FileNotFoundError, "Source world not found"):
                world_writer.schem_to_world(schem, out, source_world=missing)

    def test_source_data_version_is_clamped_to_sponge_v3_floor(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self._fake_source_world(tmp, 3105)
            schem = os.path.join(tmp, "city.schem")
            out = os.path.join(tmp, "world")
            self._write_schem(schem)

            world_writer.schem_to_world(schem, out, source_world=source)

            data = nbtlib.load(os.path.join(out, "level.dat"))["Data"]
            self.assertEqual(int(data["DataVersion"]), world_writer.HARD_FLOOR_DATA_VERSION)

    def test_export_rejects_output_inside_source_world(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self._fake_source_world(tmp, 4790)
            schem = os.path.join(tmp, "city.schem")
            out = os.path.join(source, "nested-output")
            self._write_schem(schem)

            with self.assertRaisesRegex(ValueError, "must not contain each other"):
                world_writer.schem_to_world(schem, out, source_world=source)

    def test_export_rejects_source_world_as_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self._fake_source_world(tmp, 4790)
            schem = os.path.join(tmp, "city.schem")
            self._write_schem(schem)

            with self.assertRaisesRegex(ValueError, "must be different"):
                world_writer.schem_to_world(schem, source, source_world=source)

    def test_export_rejects_source_world_inside_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_parent = os.path.join(tmp, "output")
            os.makedirs(output_parent)
            source = self._fake_source_world(output_parent, 4790)
            schem = os.path.join(tmp, "city.schem")
            self._write_schem(schem)

            with self.assertRaisesRegex(ValueError, "must not contain each other"):
                world_writer.schem_to_world(schem, output_parent, source_world=source)


if __name__ == "__main__":
    unittest.main()
