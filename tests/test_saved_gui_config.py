import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gui.core import common


class SavedGuiConfigTests(unittest.TestCase):
    def test_save_and_load_saved_gui_config(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config_dir = Path(tempdir) / "src" / "config"
            config_path = config_dir / "config_citygen.json"
            sample = {
                "preview": {"seed": "12", "algo": {"FINE": "Big"}},
                "extraction": {"world_path": "C:/world"},
            }

            with mock.patch.object(common, "SAVED_GUI_CONFIG_PATH", str(config_path)):
                common.save_saved_gui_config(sample)
                loaded = common.load_saved_gui_config()

            self.assertEqual(loaded, sample)

    def test_load_saved_gui_config_migrates_legacy_root_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config_dir = Path(tempdir) / "src" / "config"
            config_path = config_dir / "config_citygen.json"
            legacy_path = Path(tempdir) / "citygen_saved_config.json"
            sample = {"render": {"seed": "4"}}
            legacy_path.write_text('{"render": {"seed": "4"}}', encoding="utf-8")

            with (
                mock.patch.object(common, "SAVED_GUI_CONFIG_PATH", str(config_path)),
                mock.patch.object(common, "LEGACY_SAVED_GUI_CONFIG_PATH", str(legacy_path)),
            ):
                loaded = common.load_saved_gui_config()

            self.assertEqual(loaded, sample)
            self.assertTrue(config_path.exists())
            self.assertFalse(legacy_path.exists())

    def test_default_algo_tab_config_contains_seed_and_algo(self):
        config = common.default_algo_tab_config()

        self.assertEqual(config["seed"], str(common.DEFAULT_SEED))
        self.assertIn("FINE", config["algo"])
        self.assertIn("GAP_MIXED", config["algo"])

    def test_default_extraction_tab_config_contains_all_regions(self):
        config = common.default_extraction_tab_config()

        self.assertIn("world_path", config)
        self.assertIn("road", config)
        self.assertIn("house", config)
        self.assertIn("landmark", config)
        self.assertEqual(len(config["road"]["start"]), 3)
        self.assertEqual(len(config["road"]["end"]), 3)


if __name__ == "__main__":
    unittest.main()
