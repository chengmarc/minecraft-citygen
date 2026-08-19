import unittest

import numpy as np

from engine.render_isometric import render_grid_visible_iso


class IsometricRendererTests(unittest.TestCase):
    def test_render_grid_visible_iso_returns_rgba_image(self):
        inv = {
            0: "minecraft:air",
            1: "minecraft:stone",
        }
        grid = np.zeros((2, 2, 2), dtype=np.int32)
        grid[0, 0, 0] = 1
        grid[0, 1, 0] = 1
        image = render_grid_visible_iso(grid, inv, tile_w=8, tile_h=4, block_h=4, margin=2)
        self.assertEqual(image.mode, "RGBA")
        self.assertGreater(image.width, 0)
        self.assertGreater(image.height, 0)


if __name__ == "__main__":
    unittest.main()
