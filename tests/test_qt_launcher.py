import unittest
from unittest import mock

from gui import common, launcher


class QtViewerLaunchTests(unittest.TestCase):
    def test_launcher_routes_default_to_qt_app(self):
        with mock.patch("gui.qt_app.main", return_value=23) as qt_main:
            result = launcher.main([])

        self.assertEqual(result, 23)
        qt_main.assert_called_once_with([])


class AlgoConfigValueTests(unittest.TestCase):
    def test_build_algo_env_from_values_maps_combo_labels(self):
        values = common.create_config_values()
        values["FINE"] = "Small"
        values["GAP_MIXED"] = "Dense"
        values["GAP_BIG"] = "7"

        env = common.build_algo_env_from_values(values)

        self.assertEqual(env["MC_CITY_FINE"], common.CANVAS_SIZE_OPTIONS["Small"])
        self.assertEqual(env["MC_CITY_GAP_MIXED"], common.CLEARANCE_OPTIONS["Dense"])
        self.assertEqual(env["MC_CITY_GAP_BIG"], "7")


if __name__ == "__main__":
    unittest.main()
