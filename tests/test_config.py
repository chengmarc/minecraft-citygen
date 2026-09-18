"""Configuration layer: env parsing and version compatibility."""
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from config import world as config_world


# --- config.world env parsing ---------------------------------------------

class WorldConfigEnvTests(unittest.TestCase):
    def test_config_world_accepts_new_and_legacy_env_formats(self):
        original = importlib.import_module("config.world")
        try:
            with mock.patch.dict(
                os.environ,
                {
                    "MC_CITY_ROAD_BOX": "((1, 2, 3), (4, 5, 6))",
                    "MC_CITY_BUILD_TYPES": "1, ((7, 8, 9), (10, 11, 12)); 2, 13, 16, 15, 18, 14, 17",
                },
                clear=False,
            ):
                config_world = importlib.reload(original)

            self.assertEqual(config_world.ROAD_BOX.as_tuple(), ((1, 2, 3), (4, 5, 6)))
            self.assertEqual(config_world.BUILD_TYPES[0].as_tuple(), (1, (7, 8, 9), (10, 11, 12)))
            self.assertEqual(config_world.BUILD_TYPES[1].as_tuple(), (2, (13, 14, 15), (16, 17, 18)))
        finally:
            importlib.reload(original)

    def test_save_path_falls_back_to_default_when_env_override_is_empty(self):
        original = importlib.import_module("config.world")
        try:
            with mock.patch.dict(os.environ, {"MC_CITY_SAVE": ""}, clear=False):
                config_world = importlib.reload(original)
            self.assertEqual(config_world.SAVE, config_world.DEFAULT_WORLD)
        finally:
            importlib.reload(original)


# --- version detection ----------------------------------------------------

class VersionTests(unittest.TestCase):
    def test_supported_data_version_floor_is_sponge_v3_floor(self):
        self.assertEqual(config_world.HARD_FLOOR_DATA_VERSION, 4790)  # Minecraft 26.1.2

    def test_detect_world_data_version_reads_bundled_world(self):
        world = Path(__file__).resolve().parents[1] / "src" / "config" / "default_world"
        self.assertEqual(config_world.detect_world_data_version(str(world)), 4790)  # bundled world is 26.1.2

    def test_detect_world_data_version_is_none_without_a_readable_level_dat(self):
        with tempfile.TemporaryDirectory() as tempdir:
            self.assertIsNone(config_world.detect_world_data_version(""))
            self.assertIsNone(config_world.detect_world_data_version(tempdir))  # no level.dat
            (Path(tempdir) / "level.dat").write_bytes(b"not a real nbt file")
            self.assertIsNone(config_world.detect_world_data_version(tempdir))  # corrupt

if __name__ == "__main__":
    unittest.main()
