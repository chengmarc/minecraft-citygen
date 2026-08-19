import importlib
import os
import unittest
from unittest import mock

from config.models import BlockRegion, BuildRegion


class RegionModelTests(unittest.TestCase):
    def test_block_region_tuple_and_env_use_xyz_pairs(self):
        region = BlockRegion.from_xyz_pair((1, 2, 3), (4, 5, 6))

        self.assertEqual(region.as_tuple(), ((1, 2, 3), (4, 5, 6)))
        self.assertEqual(region.to_env_value(), "((1, 2, 3), (4, 5, 6))")

    def test_block_region_from_values_accepts_legacy_flat_shape(self):
        region = BlockRegion.from_values((1, 4, 3, 6, 2, 5))

        self.assertEqual(region.as_tuple(), ((1, 2, 3), (4, 5, 6)))

    def test_build_region_tuple_and_env_use_xyz_pairs(self):
        region = BuildRegion.from_values((2, (1, 2, 3), (4, 5, 6)))

        self.assertEqual(region.as_tuple(), (2, (1, 2, 3), (4, 5, 6)))
        self.assertEqual(region.to_env_value(), "2, ((1, 2, 3), (4, 5, 6))")

    def test_config_world_accepts_new_and_legacy_env_formats(self):
        module_name = "config.config_world"
        original_module = importlib.import_module(module_name)

        try:
            with mock.patch.dict(
                os.environ,
                {
                    "MC_CITY_ROAD_BOX": "((1, 2, 3), (4, 5, 6))",
                    "MC_CITY_BUILD_TYPES": "1, ((7, 8, 9), (10, 11, 12)); 2, 13, 16, 15, 18, 14, 17",
                },
                clear=False,
            ):
                config_world = importlib.reload(original_module)

            self.assertEqual(config_world.ROAD_BOX.as_tuple(), ((1, 2, 3), (4, 5, 6)))
            self.assertEqual(config_world.BUILD_TYPES[0].as_tuple(), (1, (7, 8, 9), (10, 11, 12)))
            self.assertEqual(config_world.BUILD_TYPES[1].as_tuple(), (2, (13, 14, 15), (16, 17, 18)))
        finally:
            importlib.reload(original_module)


if __name__ == "__main__":
    unittest.main()
