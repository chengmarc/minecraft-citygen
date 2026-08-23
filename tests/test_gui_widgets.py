import os
import unittest

# Qt widgets need a platform plugin; run headless so the suite works in CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from gui import app as gui_app  # noqa: E402
from gui.core import common  # noqa: E402
from gui.core.theme import configure_app_style  # noqa: E402
from gui.widgets.widgets import AlgoControlsWidget, IntegerSliderControl  # noqa: E402


def _qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class ArgParsingTests(unittest.TestCase):
    def test_defaults(self):
        options, qt_args = gui_app._parse_args([])
        self.assertIsNone(options.style_name)
        self.assertTrue(options.use_custom_theme)
        self.assertEqual(qt_args, [])

    def test_style_and_no_custom_theme_with_passthrough(self):
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

    def test_plain_theme_clears_stylesheet(self):
        configure_app_style(self.app, use_custom_theme=False)
        self.assertEqual(self.app.styleSheet(), "")

    def test_custom_theme_applies_stylesheet(self):
        configure_app_style(self.app, use_custom_theme=True)
        self.assertIn("QPushButton", self.app.styleSheet())
        self.app.setStyleSheet("")  # avoid leaking into other tests


class IntegerSliderControlTests(unittest.TestCase):
    def setUp(self):
        self.app = _qapp()

    def test_value_round_trip_and_label(self):
        slider = IntegerSliderControl(0, 10, 3)
        self.assertEqual(slider.value(), 3)
        self.assertEqual(slider.value_label.text(), "3")
        slider.setValue(7)
        self.assertEqual(slider.value(), 7)
        self.assertEqual(slider.value_label.text(), "7")


class AlgoControlsWidgetTests(unittest.TestCase):
    def setUp(self):
        self.app = _qapp()

    def test_default_state_round_trips_through_env(self):
        state = common.default_algo_tab_config()
        controls = AlgoControlsWidget("Preview", lambda: None, state)

        values = controls.algo_values()
        for name, _label, _description in common.PREVIEW_CONFIGS:
            self.assertIn(name, values)

        current = controls.current_state()
        self.assertEqual(current["seed"], state["seed"])
        self.assertEqual(set(current["algo"]), set(values))

        env = common.build_algo_env_from_values(values)
        self.assertIn("MC_CITY_FINE", env)
        self.assertIn("MC_CITY_GAP_MIXED", env)


if __name__ == "__main__":
    unittest.main()
