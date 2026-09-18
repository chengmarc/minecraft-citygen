"""GUI launch workflows: gating, saved state, and pipeline handoffs."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Qt widgets need a platform plugin; run headless so the suite works in CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from config.path import city_preview_path, grid_preview_path  # noqa: E402
from gui import app as gui_app  # noqa: E402
from gui import launcher  # noqa: E402
from gui.core import algo_config, app_files, extraction_config, progress  # noqa: E402
from gui.tabs import extraction as extraction_module  # noqa: E402
from gui.tabs import generation as generation_module  # noqa: E402
from gui.tabs import preview as preview_module  # noqa: E402
from gui.tabs.extraction import ExtractionTab  # noqa: E402
from gui.tabs.generation import GenerationTab  # noqa: E402
from gui.tabs.preview import PreviewTab  # noqa: E402
from pipeline import stages  # noqa: E402


def _qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _GuiOwner(QtWidgets.QWidget):
    def __init__(self, **sections):
        super().__init__()
        self._sections = sections
        self.events = []

    def get_saved_config_section(self, section):
        return self._sections.get(section)

    def set_saved_config_section(self, section, value):
        self._sections[section] = value

    def refresh_prerequisite_buttons(self):
        self.events.append("refresh_prerequisites")


class _ImmediateThread:
    def __init__(self, target, **_kwargs):
        self._target = target

    def start(self):
        self._target()


class LauncherTests(unittest.TestCase):
    def test_launcher_routes_default_to_qt_app(self):
        with mock.patch("gui.app.main", return_value=23) as qt_main:
            result = launcher.main([])

        self.assertEqual(result, 23)
        qt_main.assert_called_once_with([])

    def test_parse_args_keeps_qt_passthrough_args(self):
        options, qt_args = gui_app._parse_args(["--qt-style", "Fusion", "-platform", "offscreen"])

        self.assertEqual(options.style_name, "Fusion")
        self.assertEqual(qt_args, ["-platform", "offscreen"])


class LaunchGatingTests(unittest.TestCase):
    def setUp(self):
        self.app = _qapp()

    def test_first_launch_requires_extracted_assets_before_preview_or_build(self):
        with (
            mock.patch.object(app_files, "load_saved_gui_config", return_value={}),
            mock.patch.object(app_files, "clear_pipeline_artifacts"),
            mock.patch.object(app_files, "extracted_assets_ready", return_value=False),
        ):
            window = gui_app.CityGeneratorQtApp()

        self.assertFalse(window.preview_tab.controls.action_button.isEnabled())
        self.assertFalse(window.generation_tab.controls.action_button.isEnabled())
        self.assertTrue(window.extraction_tab.extract_button.isEnabled())

        with mock.patch.object(app_files, "extracted_assets_ready", return_value=True):
            window.refresh_prerequisite_buttons()

        self.assertTrue(window.preview_tab.controls.action_button.isEnabled())
        self.assertTrue(window.generation_tab.controls.action_button.isEnabled())
        window.close()


class GuiPipelineHandoffTests(unittest.TestCase):
    def setUp(self):
        self.app = _qapp()

    def test_extraction_run_builds_env_and_runs_road_then_build_stages(self):
        owner = _GuiOwner(extraction=extraction_config.default_extraction_tab_config())
        calls = []

        progress_stage = {"roads": stages.ROADS_EXTRACT, "builds": stages.BUILDS_EXTRACT}

        def fake_stage(name, *, env_overrides, progress=None):
            calls.append((name, dict(env_overrides)))
            if progress is not None:
                progress(progress_stage[name], 1, 1, "done")
            return {"stage": name}

        with (
            mock.patch.object(extraction_module, "has_region_files", return_value=True),
            mock.patch.object(extraction_module.extraction_config, "stamp_version_env", return_value={"MC_CITY_DATA_VERSION": "4790"}),
            mock.patch.object(extraction_module.services, "run_stage", side_effect=fake_stage),
            mock.patch.object(extraction_module.threading, "Thread", _ImmediateThread),
            mock.patch.object(extraction_module.app_files, "save_progress_timing"),
        ):
            tab = ExtractionTab(owner)
            tab.road_viewer.load_image = lambda _path: None
            tab.build_viewer.load_image = lambda _path: None
            tab._run_extract_all()

        self.assertEqual([name for name, _env in calls], ["roads", "builds"])
        env = calls[0][1]
        self.assertEqual(calls[1][1], env)
        self.assertEqual(env["MC_CITY_SAVE"], owner._sections["extraction"]["world_path"])
        self.assertIn("MC_CITY_ROAD_BOX", env)
        self.assertIn("MC_CITY_BUILD_TYPES", env)
        self.assertEqual(env["MC_CITY_DATA_VERSION"], "4790")
        self.assertIn("refresh_prerequisites", owner.events)
        tab.close()
        owner.close()

    def test_preview_run_passes_seed_size_and_algorithm_env_to_service(self):
        owner = _GuiOwner(algo=algo_config.default_algo_tab_config())
        calls = {}

        def fake_preview(stage_key, *, seed, fine, env_overrides, progress=None, logger=None):
            calls.update(stage=stage_key, seed=seed, fine=fine, env=dict(env_overrides), logger=logger)
            if progress is not None:
                progress(stages.PREVIEW_CITY, 2, 2, "Rendered city layout preview")
            return {"seed": seed}

        with (
            mock.patch.object(preview_module.services, "run_stage", side_effect=fake_preview),
            mock.patch.object(preview_module.threading, "Thread", _ImmediateThread),
        ):
            tab = PreviewTab(owner)
            loaded = []
            tab.grid_viewer.load_image = loaded.append
            tab.city_viewer.load_image = loaded.append
            tab.controls.seed_edit.setText("42")
            tab._run_preview()

        self.assertEqual(calls["stage"], "preview")
        self.assertEqual(calls["seed"], "42")
        self.assertEqual(calls["fine"], calls["env"]["MC_CITY_FINE"])
        self.assertIn("MC_CITY_GAP_BIG", calls["env"])
        self.assertEqual(loaded, [grid_preview_path("42"), city_preview_path("42")])
        tab.close()
        owner.close()

    def test_generation_run_exports_city_using_selected_source_world(self):
        extraction_state = extraction_config.default_extraction_tab_config()
        extraction_state["world_path"] = "C:/minecraft/source-world"
        owner = _GuiOwner(algo=algo_config.default_algo_tab_config(), extraction=extraction_state)
        calls = []

        progress_stage = {"city": stages.CITY_RENDER, "world": stages.WORLD_EXPORT}

        def record(name, *, seed, env_overrides, progress=None, **params):
            calls.append((name, seed, params, dict(env_overrides)))
            if progress is not None:
                progress(progress_stage[name], 1, 1, "done")
            return {"stage": name}

        with (
            mock.patch.object(generation_module.extraction_config, "stamp_version_env", return_value={"MC_CITY_DATA_VERSION": "4790"}),
            mock.patch.object(generation_module.services, "run_stage", side_effect=record),
            mock.patch.object(generation_module.threading, "Thread", _ImmediateThread),
            mock.patch.object(generation_module.app_files, "save_progress_timing"),
        ):
            tab = GenerationTab(owner)
            tab.city_viewer.load_image = lambda _path: None
            tab.controls.seed_edit.setText("9")
            tab._run_generate()

        self.assertEqual([name for name, _seed, _params, _env in calls], ["city", "world"])
        self.assertEqual(calls[0][2], {"fine": calls[0][3]["MC_CITY_FINE"]})
        self.assertEqual(calls[1][2], {})
        for _name, seed, _args, env in calls:
            self.assertEqual(seed, "9")
            self.assertEqual(env["MC_CITY_SAVE"], "C:/minecraft/source-world")
            self.assertEqual(env["MC_CITY_DATA_VERSION"], "4790")
        tab.close()
        owner.close()


class SavedGuiConfigTests(unittest.TestCase):
    def test_save_and_load_saved_gui_config(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config_path = Path(tempdir) / "src" / "config" / "citygen.json"
            sample = {
                "algo": {"seed": "12", "algo": {"FINE": "Big"}},
                "extraction": {"world_path": "C:/world"},
            }

            with mock.patch.object(app_files, "SAVED_GUI_CONFIG_PATH", str(config_path)):
                app_files.save_saved_gui_config(sample)
                loaded = app_files.load_saved_gui_config()

        self.assertEqual(loaded, sample)

    def test_load_saved_gui_config_migrates_legacy_root_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config_path = Path(tempdir) / "src" / "config" / "citygen.json"
            legacy_path = Path(tempdir) / "citygen_saved_config.json"
            sample = {"render": {"seed": "4"}}
            legacy_path.write_text('{"render": {"seed": "4"}}', encoding="utf-8")

            with (
                mock.patch.object(app_files, "SAVED_GUI_CONFIG_PATH", str(config_path)),
                mock.patch.object(app_files, "LEGACY_SAVED_GUI_CONFIG_PATH", str(legacy_path)),
            ):
                loaded = app_files.load_saved_gui_config()

            self.assertEqual(loaded, sample)
            self.assertTrue(config_path.exists())
            self.assertFalse(legacy_path.exists())


class ProgressWeightMirrorTests(unittest.TestCase):
    """GUI progress weights are hand-tuned per pipeline step; keep one per step."""

    def test_preview_weights_match_preview_stage_steps(self):
        self.assertEqual(len(progress.PREVIEW_STEP_WEIGHTS), len(stages.STAGES["preview"]))

    def test_construct_weights_match_construct_steps(self):
        construct = importlib.import_module(stages.CITY_CONSTRUCT)
        self.assertEqual(len(progress.GENERATION_CONSTRUCT_WEIGHTS), len(construct.STEPS))


if __name__ == "__main__":
    unittest.main()
