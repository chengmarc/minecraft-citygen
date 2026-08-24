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
from gui.tabs import ExtractionTab, GenerationTab, PreviewTab  # noqa: E402
from gui.tabs import extraction as extraction_module  # noqa: E402
from gui.tabs import generation as generation_module  # noqa: E402
from gui.widgets.widgets import AlgoControlsWidget, IntegerSliderControl  # noqa: E402


def _qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class LauncherTests(unittest.TestCase):
    def test_launcher_routes_default_to_qt_app(self):
        with mock.patch("gui.app.main", return_value=23) as qt_main:
            result = launcher.main([])
        self.assertEqual(result, 23)
        qt_main.assert_called_once_with([])

    def test_main_window_sets_step_tooltips_on_tabs(self):
        _qapp()
        window = gui_app.CityGeneratorQtApp()
        tabs = window.centralWidget()
        tab_bar = tabs.tabBar()
        self.assertEqual(tabs.tabText(0), "Extract Assets")
        self.assertEqual(tab_bar.tabToolTip(0), "Step 1 of 3: Choose a Minecraft world and extract road, house, and landmark assets.")
        self.assertEqual(tab_bar.tabToolTip(1), "Step 2 of 3: Test seeds and Avenue/Street settings before the final build.")
        self.assertEqual(tab_bar.tabToolTip(2), "Step 3 of 3: Build the city, render it, and export the Minecraft world.")
        window.close()


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
        self.assertIn("QPushButton:disabled {\n    background: #e3e8f0;\n    color: #ffffff;", self.app.styleSheet())
        self.assertIn("QToolButton#advancedToggle:checked:hover", self.app.styleSheet())
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
        self.assertTrue(all(key.startswith("MC_CITY_") for key in env))

    def test_algo_controls_seed_validator_present(self):
        state = common.default_algo_tab_config()
        controls = AlgoControlsWidget("Preview", lambda: None, state)
        self.assertIsNotNone(controls.seed_edit.validator())

    def test_algo_controls_use_updated_header_labels_and_seed_width(self):
        state = common.default_algo_tab_config()
        controls = AlgoControlsWidget("Preview", lambda: None, state)
        labels = {label.text() for label in controls.findChildren(QtWidgets.QLabel)}
        self.assertIn("City Size", labels)
        self.assertIn("Road Density", labels)
        self.assertEqual(controls.seed_edit.width(), 65)
        self.assertEqual(controls.advanced_toggle.minimumHeight(), controls.seed_edit.sizeHint().height())
        self.assertEqual(controls.advanced_toggle.maximumHeight(), controls.seed_edit.sizeHint().height())

    def test_algo_controls_hide_advanced_by_default_and_toggle(self):
        state = common.default_algo_tab_config()
        controls = AlgoControlsWidget("Preview", lambda: None, state)
        self.assertTrue(controls.advanced_panel.isHidden())
        self.assertEqual(controls.advanced_toggle.text(), "Basic Settings")
        controls.advanced_toggle.click()
        self.assertFalse(controls.advanced_panel.isHidden())
        self.assertEqual(controls.advanced_toggle.text(), "Advanced Settings")

    def test_algo_controls_state_round_trip_includes_advanced_toggle(self):
        state = common.default_algo_tab_config()
        controls = AlgoControlsWidget("Preview", lambda: None, state)
        controls.set_advanced_visible(True)
        snapshot = controls.current_state()

        mirror = AlgoControlsWidget("Preview", lambda: None, state)
        mirror.set_state(snapshot)
        self.assertFalse(mirror.advanced_panel.isHidden())
        self.assertTrue(mirror.advanced_toggle.isChecked())
        self.assertEqual(mirror.advanced_toggle.text(), "Advanced Settings")


class _GuiOwner(QtWidgets.QWidget):
    def __init__(self, **sections):
        super().__init__()
        self._sections = sections

    def get_saved_config_section(self, section):
        return self._sections.get(section)

    def set_saved_config_section(self, section, value):
        self._sections[section] = value


class ExtractionTabTests(unittest.TestCase):
    def setUp(self):
        self.app = _qapp()

    def test_extraction_cards_show_status_and_summary(self):
        state = common.default_extraction_tab_config()
        tab = ExtractionTab(_GuiOwner(extraction=state))
        self.assertEqual(tab.findChildren(QtWidgets.QSplitter), [])
        self.assertEqual(tab.road_group.status_chip.text(), "Selected")
        self.assertIn("chunks selected", tab.road_group.detail_label.text())
        self.assertFalse(hasattr(tab.road_group, "details_button"))
        self.assertEqual(tab.road_group.findChildren(QtWidgets.QLineEdit), [])
        self.assertEqual(tab.road_group.pick_button.sizePolicy().horizontalPolicy(), QtWidgets.QSizePolicy.Expanding)
        self.assertGreater(tab.road_group.pick_button.height(), tab.road_group.pick_button.sizeHint().height())
        tab.close()

    def test_extract_button_requires_valid_world(self):
        state = common.default_extraction_tab_config()
        state["world_path"] = ""
        with mock.patch.object(extraction_module, "has_region_files", return_value=False):
            tab = ExtractionTab(_GuiOwner(extraction=state))
            self.assertFalse(tab.extract_button.isEnabled())
            self.assertFalse(tab.road_group.pick_button.isEnabled())
        tab.close()

    def test_browsing_valid_world_clears_selected_regions(self):
        state = common.default_extraction_tab_config()
        with (
            mock.patch.object(extraction_module.QtWidgets.QFileDialog, "getExistingDirectory", return_value="C:/world"),
            mock.patch.object(extraction_module, "has_region_files", return_value=True),
            mock.patch.object(extraction_module.common, "clear_pipeline_artifacts"),
        ):
            tab = ExtractionTab(_GuiOwner(extraction=state))
            tab._browse_world()
            self.assertEqual(tab.road_group.status_chip.text(), "Not Selected")
            self.assertEqual(tab.house_group.status_chip.text(), "Not Selected")
            self.assertEqual(tab.landmark_group.status_chip.text(), "Not Selected")
            self.assertFalse(tab.extract_button.isEnabled())
            saved = tab.owner.get_saved_config_section("extraction")
            self.assertIsNone(saved["road"]["start"])
            self.assertIsNone(saved["road"]["end"])
        tab.close()

    def test_extraction_progress_uses_product_language(self):
        state = common.default_extraction_tab_config()
        with mock.patch.object(extraction_module, "has_region_files", return_value=True):
            tab = ExtractionTab(_GuiOwner(extraction=state))
        tab._on_pipeline_progress(extraction_module.services.ROADS_EXTRACT, 1, 10, "ignored")
        self.assertEqual(tab.status_label.text(), "Extracting road pieces")
        self.assertNotIn("pipeline/", tab.status_label.text())
        tab.close()

    def test_extraction_final_stage_completion_fills_progress_bar(self):
        state = common.default_extraction_tab_config()
        with mock.patch.object(extraction_module, "has_region_files", return_value=True):
            tab = ExtractionTab(_GuiOwner(extraction=state))
        tab._on_pipeline_progress(extraction_module.services.BUILDS_RENDER, 9, 9, "ignored")
        self.assertEqual(tab.progress_bar.value(), extraction_module.PROGRESS_BAR_SCALE)
        self.assertEqual(tab.status_label.text(), "Building asset sheet")
        tab.close()

    def test_browse_button_matches_world_input_height(self):
        state = common.default_extraction_tab_config()
        with mock.patch.object(extraction_module, "has_region_files", return_value=True):
            tab = ExtractionTab(_GuiOwner(extraction=state))
        self.assertEqual(tab.browse_button.minimumHeight(), tab.world_edit.sizeHint().height())
        self.assertEqual(tab.browse_button.maximumHeight(), tab.world_edit.sizeHint().height())
        tab.close()

    def test_browse_placeholder_keeps_contact_sheet_paths_for_success_reload(self):
        state = common.default_extraction_tab_config()
        with (
            mock.patch.object(extraction_module.QtWidgets.QFileDialog, "getExistingDirectory", return_value="C:/world"),
            mock.patch.object(extraction_module, "has_region_files", return_value=True),
            mock.patch.object(extraction_module.common, "clear_pipeline_artifacts"),
        ):
            tab = ExtractionTab(_GuiOwner(extraction=state))
            road_path = tab.road_viewer.image_path
            build_path = tab.build_viewer.image_path
            tab._browse_world()
            self.assertEqual(tab.road_viewer.image_path, road_path)
            self.assertEqual(tab.build_viewer.image_path, build_path)
        tab.close()


class ExtractionProgressCoalescingTests(unittest.TestCase):
    def test_coalescer_drops_redundant_updates_but_keeps_terminal_tick(self):
        emitted = []
        on_progress = extraction_module.coalesce_pipeline_progress(
            lambda stage, completed, total, label: emitted.append((stage, completed, total, label)),
            buckets=4,
        )

        for completed in (0, 1, 2, 2, 3, 4, 8, 8, 9):
            on_progress("stage", completed, 9, "label")

        self.assertEqual(
            emitted,
            [
                ("stage", 0.0, 9.0, "label"),
                ("stage", 3.0, 9.0, "label"),
                ("stage", 8.0, 9.0, "label"),
                ("stage", 9.0, 9.0, "label"),
            ],
        )


class PreviewGenerationTabTests(unittest.TestCase):
    def setUp(self):
        self.app = _qapp()

    def test_preview_prefers_shared_algo_state_over_legacy_preview_state(self):
        owner = _GuiOwner(
            algo={"seed": "11", "algo": {"FINE": "Very Big"}},
            preview={"seed": "29", "algo": {"FINE": "Very Small"}},
        )
        tab = PreviewTab(owner)
        self.assertEqual(tab.controls.seed_edit.text(), "11")
        self.assertEqual(tab.controls.widgets["FINE"].currentText(), "Very Big")
        tab.close()

    def test_generation_uses_legacy_render_state_when_shared_algo_missing(self):
        owner = _GuiOwner(
            render={"seed": "17", "algo": {"GAP_MIXED": "Sparse"}},
            extraction=common.default_extraction_tab_config(),
        )
        tab = GenerationTab(owner)
        self.assertEqual(tab.controls.seed_edit.text(), "17")
        self.assertEqual(tab.controls.widgets["GAP_MIXED"].currentText(), "Sparse")
        tab.close()

    def test_preview_tab_starts_with_advanced_controls_hidden(self):
        tab = PreviewTab(_GuiOwner(algo=common.default_algo_tab_config()))
        self.assertEqual(tab.findChildren(QtWidgets.QSplitter), [])
        self.assertTrue(tab.controls.advanced_panel.isHidden())
        self.assertEqual(tab.controls.advanced_toggle.text(), "Basic Settings")
        tab.close()

    def test_generation_progress_uses_product_language(self):
        owner = _GuiOwner(
            algo=common.default_algo_tab_config(),
            extraction=common.default_extraction_tab_config(),
        )
        tab = GenerationTab(owner)
        tab._on_pipeline_progress(generation_module.services.CITY_RENDER, 1, 2, "ignored")
        self.assertEqual(tab.status_label.text(), "Rendering final city")
        self.assertNotIn("pipeline/", tab.status_label.text())
        tab.close()

    def test_preview_button_disables_until_extraction_is_complete(self):
        owner = _GuiOwner(
            algo=common.default_algo_tab_config(),
            extraction=common.default_extraction_tab_config(),
        )
        owner.preview_prerequisite_met = lambda: False
        tab = PreviewTab(owner)
        self.assertFalse(tab.controls.action_button.isEnabled())
        self.assertIn("Complete Extract Assets first.", tab.controls.action_button.toolTip())
        tab.close()

    def test_generation_button_disables_until_extraction_is_complete(self):
        owner = _GuiOwner(
            algo=common.default_algo_tab_config(),
            extraction=common.default_extraction_tab_config(),
        )
        owner.generation_prerequisite_met = lambda: False
        tab = GenerationTab(owner)
        self.assertFalse(tab.controls.action_button.isEnabled())
        self.assertIn("Complete Extract Assets first.", tab.controls.action_button.toolTip())
        tab.close()


class StepGatingTests(unittest.TestCase):
    def setUp(self):
        self.app = _qapp()

    def test_app_requires_extracted_assets_on_first_launch(self):
        with (
            mock.patch.object(common, "load_saved_gui_config", return_value={}),
            mock.patch.object(common, "clear_pipeline_artifacts"),
            mock.patch.object(common, "extracted_assets_ready", return_value=False),
        ):
            window = gui_app.CityGeneratorQtApp()

        self.assertFalse(window.preview_tab.controls.action_button.isEnabled())
        self.assertFalse(window.generation_tab.controls.action_button.isEnabled())
        self.assertTrue(window.extraction_tab.extract_button.isEnabled())

        window.extraction_tab.world_edit.setText("C:/different-world")
        self.assertFalse(window.preview_tab.controls.action_button.isEnabled())
        self.assertFalse(window.generation_tab.controls.action_button.isEnabled())

        with mock.patch.object(common, "extracted_assets_ready", return_value=True):
            window.refresh_prerequisite_buttons()
            self.assertTrue(window.preview_tab.controls.action_button.isEnabled())
            self.assertTrue(window.generation_tab.controls.action_button.isEnabled())

        window.close()

    def test_successful_extraction_enables_preview_when_contact_sheets_exist(self):
        with (
            mock.patch.object(common, "load_saved_gui_config", return_value={}),
            mock.patch.object(common, "clear_pipeline_artifacts"),
            mock.patch.object(common, "extracted_assets_ready", return_value=False),
        ):
            window = gui_app.CityGeneratorQtApp()

        with mock.patch.object(common, "extracted_assets_ready", return_value=True):
            window.mark_extraction_complete(window.extraction_tab.prerequisite_state())
        self.assertTrue(window.preview_tab.controls.action_button.isEnabled())
        self.assertTrue(window.generation_tab.controls.action_button.isEnabled())
        window.close()

    def test_changing_extraction_inputs_keeps_preview_enabled_when_contact_sheets_exist(self):
        with (
            mock.patch.object(common, "load_saved_gui_config", return_value={}),
            mock.patch.object(common, "clear_pipeline_artifacts"),
            mock.patch.object(common, "extracted_assets_ready", return_value=True),
        ):
            window = gui_app.CityGeneratorQtApp()

            window.mark_extraction_complete(window.extraction_tab.prerequisite_state())
            self.assertTrue(window.preview_tab.controls.action_button.isEnabled())

            window.extraction_tab.road_group.clear_selection()
            self.assertTrue(window.preview_tab.controls.action_button.isEnabled())
            self.assertTrue(window.generation_tab.controls.action_button.isEnabled())
        window.close()

    def test_preview_and_generation_keep_advanced_toggle_in_sync(self):
        with (
            mock.patch.object(common, "load_saved_gui_config", return_value={}),
            mock.patch.object(common, "clear_pipeline_artifacts"),
        ):
            window = gui_app.CityGeneratorQtApp()

        window.preview_tab.controls.advanced_toggle.click()
        self.assertFalse(window.preview_tab.controls.advanced_panel.isHidden())
        self.assertFalse(window.generation_tab.controls.advanced_panel.isHidden())
        self.assertTrue(window.generation_tab.controls.advanced_toggle.isChecked())

        window.generation_tab.controls.advanced_toggle.click()
        self.assertTrue(window.generation_tab.controls.advanced_panel.isHidden())
        self.assertTrue(window.preview_tab.controls.advanced_panel.isHidden())
        self.assertFalse(window.preview_tab.controls.advanced_toggle.isChecked())

        window.close()


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
