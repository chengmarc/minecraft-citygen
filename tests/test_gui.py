"""GUI launch workflows: gating, saved state, and pipeline handoffs."""

from __future__ import annotations

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
from gui.tabs import ExtractionTab, GenerationTab, PreviewTab  # noqa: E402
from gui.tabs import extraction as extraction_module  # noqa: E402
from gui.tabs import generation as generation_module  # noqa: E402
from gui.tabs import preview as preview_module  # noqa: E402


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

    def preview_prerequisite_met(self):
        return True

    def generation_prerequisite_met(self):
        return True

    def begin_extraction_run(self):
        self.events.append("begin_extraction")

    def mark_extraction_complete(self, state):
        self.events.append(("extraction_complete", state))

    def end_extraction_run(self, succeeded):
        self.events.append(("end_extraction", succeeded))

    def mark_preview_complete(self, state):
        self.events.append(("preview_complete", state))


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
            mock.patch.object(common, "load_saved_gui_config", return_value={}),
            mock.patch.object(common, "clear_pipeline_artifacts"),
            mock.patch.object(common, "extracted_assets_ready", return_value=False),
        ):
            window = gui_app.CityGeneratorQtApp()

        self.assertFalse(window.preview_tab.controls.action_button.isEnabled())
        self.assertFalse(window.generation_tab.controls.action_button.isEnabled())
        self.assertTrue(window.extraction_tab.extract_button.isEnabled())

        with mock.patch.object(common, "extracted_assets_ready", return_value=True):
            window.refresh_prerequisite_buttons()

        self.assertTrue(window.preview_tab.controls.action_button.isEnabled())
        self.assertTrue(window.generation_tab.controls.action_button.isEnabled())
        window.close()


class GuiPipelineHandoffTests(unittest.TestCase):
    def setUp(self):
        self.app = _qapp()

    def test_extraction_run_builds_env_and_runs_road_then_build_stages(self):
        owner = _GuiOwner(extraction=common.default_extraction_tab_config())
        calls = []

        def fake_stage(name, progress_stage):
            def run(*, env_overrides, progress=None):
                calls.append((name, dict(env_overrides)))
                if progress is not None:
                    progress(progress_stage, 1, 1, "done")
                return {"stage": name}

            return run

        with (
            mock.patch.object(extraction_module, "has_region_files", return_value=True),
            mock.patch.object(extraction_module.common, "stamp_version_env", return_value={"MC_CITY_DATA_VERSION": "4790"}),
            mock.patch.object(
                extraction_module.services,
                "run_roads_stage",
                side_effect=fake_stage("roads", extraction_module.services.ROADS_EXTRACT),
            ),
            mock.patch.object(
                extraction_module.services,
                "run_builds_stage",
                side_effect=fake_stage("builds", extraction_module.services.BUILDS_EXTRACT),
            ),
            mock.patch.object(extraction_module.threading, "Thread", _ImmediateThread),
            mock.patch.object(extraction_module.common, "save_progress_timing"),
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
        self.assertIn("begin_extraction", owner.events)
        self.assertIn(("end_extraction", True), owner.events)
        tab.close()
        owner.close()

    def test_preview_run_passes_seed_size_and_algorithm_env_to_service(self):
        owner = _GuiOwner(algo=common.default_algo_tab_config())
        calls = {}

        def fake_preview(seed, fine, *, env_overrides, progress=None, logger=None):
            calls.update(seed=seed, fine=fine, env=dict(env_overrides), logger=logger)
            if progress is not None:
                progress(preview_module.services.PREVIEW, 4, 4, "Preview ready")
            return {"seed": seed}

        with (
            mock.patch.object(preview_module.services, "run_preview_stage", side_effect=fake_preview),
            mock.patch.object(preview_module.threading, "Thread", _ImmediateThread),
        ):
            tab = PreviewTab(owner)
            tab.grid_viewer.load_image = lambda _path: None
            tab.city_viewer.load_image = lambda _path: None
            tab.controls.seed_edit.setText("42")
            tab._run_preview()

        self.assertEqual(calls["seed"], "42")
        self.assertEqual(calls["fine"], calls["env"]["MC_CITY_FINE"])
        self.assertIn("MC_CITY_GAP_BIG", calls["env"])
        self.assertEqual(owner.events[0][0], "preview_complete")
        tab.close()
        owner.close()

    def test_generation_run_exports_city_using_selected_source_world(self):
        extraction_state = common.default_extraction_tab_config()
        extraction_state["world_path"] = "C:/minecraft/source-world"
        owner = _GuiOwner(algo=common.default_algo_tab_config(), extraction=extraction_state)
        calls = []

        def record(name):
            def run(seed, *args, env_overrides, progress=None, **_kwargs):
                calls.append((name, seed, args, dict(env_overrides)))
                if progress is not None:
                    progress(name, 1, 1, "done")
                return {"stage": name}

            return run

        with (
            mock.patch.object(generation_module.common, "stamp_version_env", return_value={"MC_CITY_DATA_VERSION": "4790"}),
            mock.patch.object(generation_module.services, "run_city_stage", side_effect=record("city")),
            mock.patch.object(generation_module.services, "run_world_stage", side_effect=record("world")),
            mock.patch.object(generation_module.threading, "Thread", _ImmediateThread),
            mock.patch.object(generation_module.common, "save_progress_timing"),
        ):
            tab = GenerationTab(owner)
            tab.city_viewer.load_image = lambda _path: None
            tab.controls.seed_edit.setText("9")
            tab._run_generate()

        self.assertEqual([name for name, _seed, _args, _env in calls], ["city", "world"])
        self.assertEqual(calls[0][2], (calls[0][3]["MC_CITY_FINE"],))
        self.assertEqual(calls[1][2], ())
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


if __name__ == "__main__":
    unittest.main()
