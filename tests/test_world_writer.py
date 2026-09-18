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
from PIL import Image

from config.path import APP_ICON, resolve_region_dir
from config.world import HARD_FLOOR_DATA_VERSION
from engine.blocks import AIR_BLOCKS, parse_state
from engine.schematic.transform import BlockEntity
from engine.schematic.writer import write_sponge_schem_grid
from engine.world.anvil_world_reader import World
from engine.world import writer as world_writer

STONE = "minecraft:stone"
STAIRS = "minecraft:oak_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]"
SIGN = "minecraft:oak_sign[rotation=0,waterlogged=false]"
DATA_VERSION = 4790  # 26.1.2
# write_world anchors the grid's centre column (9, 9) at world x=0, z=0.
ANCHOR = 9


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


def _comparable(block):
    """``(name, props)`` with every air variant as plain air and no-props as None."""
    name, props = block
    return ("minecraft:air", None) if name in AIR_BLOCKS else (name, props or None)


class WorldWriterRoundTripTests(unittest.TestCase):
    def test_every_block_survives_the_round_trip(self):
        grid, inv, block_entities = _sample_grid()
        base_y = 64
        positions = list(np.ndindex(grid.shape))  # (y, z, x)
        with tempfile.TemporaryDirectory() as out:
            world_writer.write_world(grid, inv, block_entities, out, DATA_VERSION, base_y)
            world = World(region_dir=resolve_region_dir(out), save_path=out)
            read = {(y, z, x): world.block(x - ANCHOR, y + base_y, z - ANCHOR) for y, z, x in positions}

        expected = {pos: _comparable(parse_state(inv[int(grid[pos])])) for pos in positions}
        self.maxDiff = None  # show which blocks differ
        self.assertEqual({pos: _comparable(block) for pos, block in read.items()}, expected)

    def test_block_entity_survives_with_absolute_coords(self):
        grid, inv, block_entities = _sample_grid()
        base_y = 64
        with tempfile.TemporaryDirectory() as out:
            world_writer.write_world(grid, inv, block_entities, out, DATA_VERSION, base_y)
            world = World(region_dir=resolve_region_dir(out), save_path=out)
            chunk = world.load_chunk(-1, -1)  # sign at world (-1, 65, -1) -> chunk (-1, -1)
            entries = [be for be in chunk["block_entities"]
                       if (int(be["x"]), int(be["y"]), int(be["z"])) == (-1, 65, -1)]
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

    def _export(self, tmp, **kwargs):
        """Write the sample schem and export it; return the output world dir."""
        schem = os.path.join(tmp, "city.schem")
        out = os.path.join(tmp, "world")
        self._write_schem(schem)
        world_writer.schem_to_world(schem, out, **kwargs)
        return out

    def test_exported_world_is_stamped_with_the_schematic_data_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self._export(tmp, world_name="Minecraft CityGen World 5")
            data = nbtlib.load(os.path.join(out, "level.dat"))["Data"]

        # World version matches the schematic's own stamp, not the ambient env.
        self.assertEqual(int(data["DataVersion"]), DATA_VERSION)

    def test_exported_world_spawns_player_on_solid_ground(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self._export(tmp)
            data = nbtlib.load(os.path.join(out, "level.dat"))["Data"]
            px, py, pz = (float(v) for v in data["Player"]["Pos"])
            world = World(region_dir=resolve_region_dir(out), save_path=out)
            below_feet = world.block(int(px), int(py) - 1, int(pz))[0]

        self.assertNotIn(below_feet, AIR_BLOCKS)  # no void drop

    def test_exported_world_writes_the_given_icon_at_64px(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self._export(tmp, icon_path=APP_ICON)
            with Image.open(os.path.join(out, "icon.png")) as im:
                size = im.size

        self.assertEqual(size, (64, 64))

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

    def test_export_keeps_source_level_dat_native(self):
        # The export keeps the source world's native version, worldgen, packs, and
        # player state, and copies the rest of the save alongside.
        with tempfile.TemporaryDirectory() as tmp:
            source = self._fake_source_world(tmp, 4790)  # 26.1.2
            out = self._export(tmp, source_world=source)
            data = nbtlib.load(os.path.join(out, "level.dat"))["Data"]
            data_dir_copied = os.path.exists(os.path.join(out, "data", "marker.txt"))

        wgs = data["WorldGenSettings"]
        native = {
            "DataVersion": int(data["DataVersion"]),
            "Version.Id": int(data["Version"]["Id"]),
            "seed": int(wgs["seed"]),
            "dimensions": sorted(str(k) for k in wgs["dimensions"]),
            "overworld generator": str(wgs["dimensions"]["minecraft:overworld"]["generator"]["type"]),
            "enabled packs": [str(p) for p in data["DataPacks"]["Enabled"]],
            "SeenCredits": int(data["Player"]["SeenCredits"]),
            "data dir copied": data_dir_copied,
        }
        self.assertEqual(native, {
            "DataVersion": 4790,
            "Version.Id": 4790,
            "seed": 12345,
            "dimensions": ["minecraft:overworld", "minecraft:the_nether"],
            "overworld generator": "minecraft:noise",
            "enabled packs": ["vanilla", "myworldpack"],
            "SeenCredits": 1,
            "data dir copied": True,
        })

    def test_export_renames_save_and_recenters_player_in_the_overworld(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self._fake_source_world(tmp, 4790)  # player saved in the nether
            out = self._export(tmp, source_world=source, world_name="Minecraft CityGen World 7")
            data = nbtlib.load(os.path.join(out, "level.dat"))["Data"]

        self.assertEqual(
            (str(data["LevelName"]), str(data["Player"]["Dimension"]),
             (int(data["SpawnX"]), int(data["SpawnY"]), int(data["SpawnZ"]))),
            ("Minecraft CityGen World 7", "minecraft:overworld", (0, 65, 0)),
        )

    def test_source_without_player_still_gets_centered_spawn(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self._fake_source_world(tmp, 4790, include_player=False)
            schem = os.path.join(tmp, "city.schem")
            out = os.path.join(tmp, "world")
            self._write_schem(schem)

            world_writer.schem_to_world(schem, out, source_world=source, world_name="Minecraft CityGen World 9")  # must not raise

            data = nbtlib.load(os.path.join(out, "level.dat"))["Data"]
            self.assertEqual(str(data["LevelName"]), "Minecraft CityGen World 9")
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
            self.assertEqual(int(data["DataVersion"]), HARD_FLOOR_DATA_VERSION)

    def test_export_rejects_source_and_output_paths_that_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            schem = os.path.join(tmp, "city.schem")
            self._write_schem(schem)

            source = self._fake_source_world(tmp, 4790)
            output_parent = os.path.join(tmp, "output")
            os.makedirs(output_parent)
            nested_source = self._fake_source_world(output_parent, 4790)

            cases = [
                (source, os.path.join(source, "nested-output"), "must not contain each other"),
                (source, source, "must be different"),
                (nested_source, output_parent, "must not contain each other"),
            ]
            for source_world, out, message in cases:
                with self.subTest(source_world=source_world, out=out):
                    with self.assertRaisesRegex(ValueError, message):
                        world_writer.schem_to_world(schem, out, source_world=source_world)


if __name__ == "__main__":
    unittest.main()
