"""The GUI's Python side: what the page gets on load, how runs hand off to the pipeline, and what the server serves.

The bridge is plain Python, so these run without pywebview or a window.
"""

from __future__ import annotations

import importlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from config.algo import ALGO
from config.world import BlockRegion
from gui import algo as algo_module
from gui import extract as extract_module
from gui import files, progress, server
from gui.bridge import Api
from pipeline import stages


class _ImmediateThread:
    def __init__(self, target, args=(), **_kwargs):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


class _ApiTestCase(unittest.TestCase):
    """An :class:`Api` over in-memory settings, running jobs inline and recording its events."""

    saved_config = {}

    def setUp(self):
        self.saved = []
        self.events = []
        self.picked = None
        patches = [
            mock.patch.object(files, "load_saved_gui_config", return_value=dict(self.saved_config)),
            mock.patch.object(files, "save_saved_gui_config", side_effect=lambda c: self.saved.append(dict(c))),
            mock.patch.object(files, "save_progress_timing"),
            mock.patch.object(files, "extracted_assets_ready", return_value=True),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.api = Api(
            lambda event, payload: self.events.append((event, payload)),
            pick_folder=lambda _initial: self.picked,
            thread_factory=_ImmediateThread,
        )

    def event_names(self):
        return [event for event, _payload in self.events]

    def last(self, event):
        return [payload for name, payload in self.events if name == event][-1]


class LaunchGatingTests(_ApiTestCase):
    def test_first_launch_requires_extracted_assets_before_preview_or_build(self):
        with mock.patch.object(files, "extracted_assets_ready", return_value=False):
            gates = self.api.bootstrap()["gates"]

        self.assertEqual(gates, {"extract": True, "preview": False, "build": False})  # the bundled world and areas

    def test_first_launch_starts_from_the_default_settings(self):
        boot = self.api.bootstrap()

        self.assertEqual(boot["algo"], algo_module.default_algo_tab_config())
        self.assertTrue(boot["extraction"]["worldReady"])
        self.assertTrue(all(area["chunks"] for area in boot["extraction"]["areas"].values()))

    def test_form_covers_every_grouped_knob_and_both_selectors(self):
        form = self.api.bootstrap()["form"]

        self.assertEqual([s["name"] for s in form["selectors"]], list(algo_module.SELECTOR_OPTIONS))
        grouped = [field["name"] for group in form["groups"] for field in group["fields"]]
        self.assertEqual(grouped, [name for _title, names in algo_module.PREVIEW_CONFIG_GROUPS for name in names])


class ExtractTests(_ApiTestCase):
    def test_extraction_run_passes_source_and_regions_to_road_then_build_stages(self):
        calls = []
        progress_stage = {"roads": stages.ROADS_EXTRACT, "builds": stages.BUILDS_EXTRACT}

        def fake_stage(name, *, progress=None, **params):
            calls.append((name, params))
            progress(progress_stage[name], 1, 1, "done")

        with mock.patch.object(extract_module.services, "run_stage", side_effect=fake_stage):
            self.assertEqual(self.api.run_extract(), {})

        self.assertEqual([name for name, _params in calls], ["roads", "builds"])
        roads, builds = calls[0][1], calls[1][1]
        world_path = extract_module.default_extraction_tab_config()["world_path"]
        self.assertEqual(set(roads), {"save", "road_box"})
        self.assertEqual(set(builds), {"save", "build_types"})
        self.assertEqual(roads["save"], world_path)
        self.assertEqual(builds["save"], world_path)
        self.assertIsInstance(roads["road_box"], BlockRegion)
        self.assertEqual([region.build_type for region in builds["build_types"]], [1, 2])
        self.assertEqual(self.event_names()[0], "progress")
        self.assertEqual(self.event_names()[-2:], ["done", "finished"])
        files.save_progress_timing.assert_called_once()

    def test_extract_needs_all_three_areas(self):
        self.api.set_area("road", [0, 0, 0], [15, 64, 15])
        state = self.saved[-1]["extraction"]
        state["house"] = {"start": None, "end": None}
        with mock.patch.object(files, "load_saved_gui_config", return_value={"extraction": state}):
            api = Api(lambda *_: None, pick_folder=lambda _: None, thread_factory=_ImmediateThread)

        self.assertFalse(api.bootstrap()["gates"]["extract"])
        self.assertEqual(api.run_extract()["error"]["code"], "areas_missing")

    def test_picking_a_folder_without_region_files_warns_and_changes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            self.picked = folder
            answer = self.api.browse_world()

        self.assertEqual(answer["warning"], {"code": "not_a_world", "detail": folder})
        self.assertEqual(self.saved, [])

    def test_picking_a_new_world_clears_the_areas_and_the_pipeline_artifacts(self):
        self.picked = "C:/mc/new-world"
        with (
            mock.patch.object(extract_module, "has_region_files", return_value=True),
            mock.patch.object(files, "clear_pipeline_artifacts") as clear,
        ):
            answer = self.api.browse_world()

        clear.assert_called_once()
        self.assertTrue(answer["changed"])
        self.assertEqual(answer["extraction"]["worldPath"], "C:/mc/new-world")
        self.assertFalse(any(area["chunks"] for area in answer["extraction"]["areas"].values()))
        self.assertFalse(answer["gates"]["extract"])

    def test_cancelling_the_folder_picker_changes_nothing(self):
        answer = self.api.browse_world()

        self.assertNotIn("changed", answer)
        self.assertEqual(self.saved, [])

    def test_area_reports_its_chunk_span(self):
        answer = self.api.set_area("road", [0, 60, 0], [47, 80, 31])

        self.assertEqual(answer["extraction"]["areas"]["road"]["chunks"], [3, 2])

    def test_region_map_opens_on_the_default_area_when_none_is_saved(self):
        state = extract_module.default_extraction_tab_config()
        state["landmark"] = {"start": None, "end": None}
        with mock.patch.object(files, "load_saved_gui_config", return_value={"extraction": state}):
            api = Api(lambda *_: None, pick_folder=lambda _: None, thread_factory=_ImmediateThread)

        default = extract_module.default_extraction_tab_config()["landmark"]
        self.assertEqual(api.area_bounds("landmark"), {"start": default["start"], "end": default["end"]})

    def test_world_map_reports_its_url_and_meta(self):
        meta = {"x0": 0, "x1": 255, "z0": 0, "z1": 255, "step": 2}
        png = Path(files.APP_DATA) / "world_preview" / "x.png"
        with (
            mock.patch.object(extract_module, "cached_topdown_preview", return_value=(png, meta)),
            mock.patch.object(extract_module, "image", return_value={"src": "/files/world_preview/x.png?v=1"}),
        ):
            self.assertEqual(self.api.load_world_map(), {})

        self.assertEqual(self.last("worldMap"), {"src": "/files/world_preview/x.png?v=1", "meta": meta})

    def test_extract_progress_reaches_each_phase_end(self):
        value, soft_target = extract_module.extract_progress(stages.ROADS_RENDER, "render", 4, 4)

        end = progress.weighted_milestone(
            extract_module.EXTRACT_PHASE_WEIGHT_VALUES, 3, progress.PROGRESS_BAR_SCALE,
        )
        self.assertEqual(value, end)
        self.assertIsNone(soft_target)


class PreviewTests(_ApiTestCase):
    def test_preview_run_passes_a_fresh_seed_and_the_algo_to_the_service(self):
        calls = {}

        def fake_preview(stage_key, *, seed, algo, progress=None):
            calls.update(stage=stage_key, seed=seed, algo=algo)
            progress(stages.PREVIEW_CITY, 2, 2, "Rendered city layout preview")

        state = algo_module.default_algo_tab_config()
        with mock.patch.object(algo_module.services, "run_stage", side_effect=fake_preview):
            answer = self.api.run_preview(state)

        self.assertEqual(calls["stage"], "preview")
        self.assertEqual(calls["algo"], ALGO)
        self.assertNotEqual(calls["seed"], state["seed"])
        self.assertEqual(answer["state"]["seed"], calls["seed"])
        self.assertEqual(self.saved[-1]["algo"]["seed"], calls["seed"])
        self.assertEqual(self.event_names(), ["progress", "progress", "done", "finished"])
        self.assertEqual(set(self.last("done")["images"]), {"grid", "city"})

    def test_invalid_config_returns_the_error_without_running(self):
        state = algo_module.default_algo_tab_config()
        state["algo"]["GAP_BIG"] = "lots"
        with mock.patch.object(algo_module.services, "run_stage") as run_stage:
            answer = self.api.run_preview(state)

        run_stage.assert_not_called()
        self.assertEqual(answer["error"]["code"], "invalid_config")
        self.assertEqual(self.events, [])

    def test_stage_failure_reports_and_still_finishes(self):
        with mock.patch.object(algo_module.services, "run_stage", side_effect=RuntimeError("no roads")):
            self.api.run_preview(algo_module.default_algo_tab_config())

        self.assertEqual(self.event_names(), ["progress", "failed", "finished"])
        self.assertEqual(self.last("failed")["detail"], "no roads")

    def test_reset_saves_and_returns_the_defaults(self):
        state = self.api.reset_algo()

        self.assertEqual(state, algo_module.default_algo_tab_config())
        self.assertEqual(self.saved[-1]["algo"], state)


class BuildTests(_ApiTestCase):
    saved_config = {"extraction": {**extract_module.default_extraction_tab_config(), "world_path": "C:/mc/source-world"}}

    def test_build_run_exports_city_using_the_selected_source_world(self):
        calls = []
        progress_stage = {"city": stages.CITY_RENDER, "world": stages.WORLD_EXPORT}

        def record(name, *, seed, progress=None, **params):
            calls.append((name, seed, params))
            progress(progress_stage[name], 1, 1, "done")

        state = {**algo_module.default_algo_tab_config(), "seed": "9"}
        with (
            mock.patch.object(algo_module, "source_data_version", return_value=4790),
            mock.patch.object(algo_module.services, "run_stage", side_effect=record),
        ):
            self.assertEqual(self.api.run_build(state), {})

        self.assertEqual([name for name, _seed, _params in calls], ["city", "world"])
        self.assertEqual(calls[0][2], {"algo": ALGO, "data_version": 4790})
        self.assertEqual(calls[1][2], {"save": "C:/mc/source-world"})
        self.assertEqual([seed for _name, seed, _params in calls], ["9", "9"])
        self.assertEqual(self.event_names()[-2:], ["done", "finished"])
        files.save_progress_timing.assert_called_once()


class ProgressWeightMirrorTests(unittest.TestCase):
    """Progress weights are hand-tuned per pipeline step; keep one per step."""

    def test_preview_weights_match_preview_stage_steps(self):
        self.assertEqual(len(progress.PREVIEW_STEP_WEIGHTS), len(stages.STAGES["preview"]))

    def test_construct_weights_match_construct_steps(self):
        construct = importlib.import_module(stages.CITY_CONSTRUCT)
        self.assertEqual(len(progress.GENERATION_CONSTRUCT_WEIGHTS), len(construct.STEPS))

    def test_run_bar_segments_span_every_weight_once(self):
        for segments, weights in (
            (progress.EXTRACTION_SEGMENTS, progress.EXTRACTION_PHASE_WEIGHTS),
            (progress.PREVIEW_SEGMENTS, progress.PREVIEW_STEP_WEIGHTS),
            (progress.GENERATION_SEGMENTS, progress.GENERATION_WEIGHTS),
        ):
            self.assertEqual(sum(count for _label, count in segments), len(weights))

    def test_run_bar_segments_tile_the_whole_bar(self):
        for spans in progress.run_segments().values():
            self.assertEqual(spans[0]["start"], 0)
            self.assertAlmostEqual(spans[-1]["end"], 100)
            for before, after in zip(spans, spans[1:]):
                self.assertEqual(before["end"], after["start"])

    def test_build_progress_names_only_the_construction_steps(self):
        _value, _soft, detail = algo_module.build_progress(stages.CITY_CONSTRUCT, 5, 8, "Composing voxel grid")
        _value, _soft, render_detail = algo_module.build_progress(stages.CITY_RENDER, 0, 1, "done")

        self.assertEqual(detail, "Composing voxel grid")
        self.assertIsNone(render_detail)

    def test_preview_progress_creeps_toward_the_next_item(self):
        value, soft_target, _status = algo_module.preview_progress(stages.PREVIEW_CITY, 1, 2)

        step = algo_module.PREVIEW_STEPS[stages.PREVIEW_CITY][0]
        expected = progress.weighted_item_milestone(
            progress.PREVIEW_STEP_WEIGHTS, step, 1, 2, progress.PROGRESS_BAR_SCALE,
        )
        self.assertAlmostEqual(value, expected)
        self.assertGreater(soft_target, value)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "previews").mkdir()
        (self.root / "previews" / "seed 1.png").write_bytes(b"\x89PNG")
        (self.root.parent / f"{self.root.name}-secret.txt").write_text("no")
        self.addCleanup((self.root.parent / f"{self.root.name}-secret.txt").unlink)
        patches = [
            mock.patch.object(server, "APP_DATA", str(self.root)),
            mock.patch.dict(server.ROUTES, {"/files/": self.root}),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def get(self, path):
        status = []
        body = server.app({"PATH_INFO": path, "REQUEST_METHOD": "GET", "wsgi.input": io.BytesIO()},
                          lambda s, headers: status.append((s, dict(headers))))
        return status[0][0], status[0][1], b"".join(body)

    def test_file_url_names_the_file_and_its_version(self):
        url = server.file_url(self.root / "previews" / "seed 1.png")

        self.assertTrue(url.startswith("/files/previews/seed%201.png?v="))
        self.assertEqual(self.get(url.split("?")[0])[2], b"\x89PNG")

    def test_file_url_is_none_for_a_missing_file_or_one_outside_appdata(self):
        self.assertIsNone(server.file_url(self.root / "previews" / "missing.png"))
        self.assertIsNone(server.file_url(self.root.parent / f"{self.root.name}-secret.txt"))

    def test_nothing_outside_a_route_is_served(self):
        status, _headers, _body = self.get(f"/files/../{self.root.name}-secret.txt")

        self.assertEqual(status, "404 Not Found")

    def test_the_page_serves_its_own_icons(self):
        status, headers, body = self.get("/icons/extract.png")

        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "image/png")
        self.assertTrue(body.startswith(b"\x89PNG"))

    def test_the_page_is_served_with_its_content_types(self):
        for path, content_type in (("/", "text/html"), ("/app.js", "text/javascript"), ("/app.css", "text/css")):
            status, headers, _body = self.get(path)
            self.assertEqual(status, "200 OK")
            self.assertEqual(headers["Content-Type"], content_type)


class WorldPreviewTests(unittest.TestCase):
    def test_chunk_span_counts_partial_chunks_and_negative_coordinates(self):
        self.assertEqual(extract_module.chunk_span((-1, 0, 0), (16, 0, 15)), [3, 1])


if __name__ == "__main__":
    unittest.main()
