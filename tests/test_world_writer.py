"""World export: the schem -> standalone void world writer.

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
            world = World(region_dir=os.path.join(out, "region"), save_path=out)

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
            world = World(region_dir=os.path.join(out, "region"), save_path=out)
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

    def test_void_world_and_spawn_stands_on_solid_ground(self):
        with tempfile.TemporaryDirectory() as tmp:
            schem = os.path.join(tmp, "city.schem")
            out = os.path.join(tmp, "world")
            self._write_schem(schem)

            summary = world_writer.schem_to_world(schem, out)
            self.assertGreater(summary["chunks"], 0)

            data = nbtlib.load(os.path.join(out, "level.dat"))["Data"]
            # World version matches the schematic's own stamp, not the ambient env.
            self.assertEqual(int(data["DataVersion"]), DATA_VERSION)
            # Generator is emptied to a void.
            gen = data["WorldGenSettings"]["dimensions"]["minecraft:overworld"]["generator"]
            self.assertEqual(str(gen["type"]), "minecraft:flat")
            self.assertEqual(len(gen["settings"]["layers"]), 0)
            self.assertEqual(str(gen["settings"]["biome"]), "minecraft:the_void")

            # The saved player sits one block above a solid column (no void drop).
            px, py, pz = (float(v) for v in data["Player"]["Pos"])
            world = World(region_dir=os.path.join(out, "region"), save_path=out)
            self.assertNotIn(world.block(int(px), int(py) - 1, int(pz))[0], world_writer.AIR_NAMES)

    def test_stale_world_is_cleared_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            schem = os.path.join(tmp, "city.schem")
            out = os.path.join(tmp, "world")
            self._write_schem(schem)

            os.makedirs(os.path.join(out, "region"))
            stale = os.path.join(out, "region", "r.99.99.mca")
            with open(stale, "wb") as fh:
                fh.write(b"junk")

            world_writer.schem_to_world(schem, out)
            self.assertFalse(os.path.exists(stale))


if __name__ == "__main__":
    unittest.main()
