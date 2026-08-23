"""GUI layer: launcher routing, arg/theme handling, widgets, saved config."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Qt widgets need a platform plugin; run headless so the suite works in CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from gui import app as gui_app  # noqa: E402
from gui import launcher  # noqa: E402
from gui.core import common  # noqa: E402
from gui.core.theme import configure_app_style  # noqa: E402
from gui.widgets.widgets import AlgoControlsWidget, IntegerSliderControl  # noqa: E402


def _qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class LauncherTests(unittest.TestCase):
    def test_launcher_routes_default_to_qt_app(self):
        with mock.patch("gui.app.main", return_value=23) as qt_main:
            result = launcher.main([])
        self.assertEqual(result, 23)
        qt_main.assert_called_once_with([])


class ArgParsingTests(unittest.TestCase):
    def test_parse_args_defaults_and_passthrough(self):
        options, qt_args = gui_app._parse_args([])
        self.assertIsNone(options.style_name)
        self.assertTrue(options.use_custom_theme)
        self.assertEqual(qt_args, [])

        options, qt_args = gui_app._parse_args(
            ["--qt-style", "Fusion", "--no-custom-theme", "-platform", "offscreen"]
        )
        self.assertEqual(options.style_name, "Fusion")
        self.assertFalse(options.use_custom_theme)
        self.assertEqual(qt_args, ["-platform", "offscreen"])


class ConfigureStyleTests(unittest.TestCase):
    def setUp(self):
        self.app = _qapp()

    def test_unknown_style_raises(self):
        with self.assertRaises(ValueError):
            configure_app_style(self.app, style_name="DefinitelyNotAStyle")

    def test_theme_toggles_stylesheet(self):
        configure_app_style(self.app, use_custom_theme=False)
        self.assertEqual(self.app.styleSheet(), "")
        configure_app_style(self.app, use_custom_theme=True)
        self.assertIn("QPushButton", self.app.styleSheet())
        self.app.setStyleSheet("")  # avoid leaking into other tests


class WidgetTests(unittest.TestCase):
    def setUp(self):
        self.app = _qapp()

    def test_integer_slider_value_round_trip_and_label(self):
        slider = IntegerSliderControl(0, 10, 3)
        self.assertEqual(slider.value(), 3)
        self.assertEqual(slider.value_label.text(), "3")
        slider.setValue(7)
        self.assertEqual(slider.value(), 7)
        self.assertEqual(slider.value_label.text(), "7")

    def test_algo_controls_round_trip_through_env(self):
        state = common.default_algo_tab_config()
        controls = AlgoControlsWidget("Preview", lambda: None, state)

        values = controls.algo_values()
        for name, _label, _description in common.PREVIEW_CONFIGS:
            self.assertIn(name, values)

        current = controls.current_state()
        self.assertEqual(current["seed"], state["seed"])
        self.assertEqual(set(current["algo"]), set(values))

        # Combo labels map to their env values; raw values pass through.
        values["FINE"] = "Small"
        values["GAP_MIXED"] = "Dense"
        values["GAP_BIG"] = "7"
        env = common.build_algo_env_from_values(values)
        self.assertEqual(env["MC_CITY_FINE"], common.CANVAS_SIZE_OPTIONS["Small"])
        self.assertEqual(env["MC_CITY_GAP_MIXED"], common.CLEARANCE_OPTIONS["Dense"])
        self.assertEqual(env["MC_CITY_GAP_BIG"], "7")


class SavedGuiConfigTests(unittest.TestCase):
    def test_save_and_load_saved_gui_config(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config_path = Path(tempdir) / "src" / "config" / "citygen.json"
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
            config_path = Path(tempdir) / "src" / "config" / "citygen.json"
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

    def test_default_tab_configs_contain_expected_keys(self):
        algo = common.default_algo_tab_config()
        self.assertEqual(algo["seed"], str(common.DEFAULT_SEED))
        self.assertIn("FINE", algo["algo"])
        self.assertIn("GAP_MIXED", algo["algo"])

        extraction = common.default_extraction_tab_config()
        for key in ("world_path", "road", "house", "landmark"):
            self.assertIn(key, extraction)
        self.assertEqual(len(extraction["road"]["start"]), 3)
        self.assertEqual(len(extraction["road"]["end"]), 3)


if __name__ == "__main__":
    unittest.main()
