import unittest

from engine.schematic_transform import Tile, rot_state, rot_tile


class SchematicTransformTests(unittest.TestCase):
    def test_rot_state_rotates_directional_properties(self):
        state = "minecraft:oak_stairs[east=none,facing=north,half=bottom,north=low,shape=straight,south=tall,waterlogged=false]"
        rotated = rot_state(state, 1)

        self.assertEqual(
            rotated,
            "minecraft:oak_stairs[east=low,facing=east,half=bottom,shape=straight,south=none,waterlogged=false,west=tall]",
        )

    def test_rot_tile_rotates_dimensions_and_cells(self):
        tile = Tile(
            2,
            1,
            3,
            [[
                ["a", "b"],
                ["c", "d"],
                ["minecraft:oak_log[axis=x]", "minecraft:oak_stairs[facing=north]"],
            ]],
        )

        rotated = rot_tile(tile, 1)

        self.assertEqual((rotated.W, rotated.H, rotated.L), (3, 1, 2))
        self.assertEqual(rotated.cells[0][0][0], "minecraft:oak_log[axis=z]")
        self.assertEqual(rotated.cells[0][0][1], "c")
        self.assertEqual(rotated.cells[0][0][2], "a")
        self.assertEqual(rotated.cells[0][1][0], "minecraft:oak_stairs[facing=east]")


if __name__ == "__main__":
    unittest.main()
