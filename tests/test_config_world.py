import importlib
import os
import unittest
from unittest import mock


class ConfigWorldTests(unittest.TestCase):
    def test_save_path_falls_back_to_default_when_env_override_is_empty(self):
        module_name = "config.world"
        original_module = importlib.import_module(module_name)

        try:
            with mock.patch.dict(os.environ, {"MC_CITY_SAVE": ""}, clear=False):
                config_world = importlib.reload(original_module)
            self.assertEqual(config_world.SAVE, config_world.DEFAULT_WORLD)
        finally:
            importlib.reload(original_module)


if __name__ == "__main__":
    unittest.main()
