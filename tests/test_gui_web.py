"""The GUI's Python side: what the page gets on load, how runs hand off to the pipeline, and what the server serves.

The bridge is plain Python, so these run without pywebview or a window.
"""

from __future__ import annotations

import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from citygen import render_topdown, step1_extract, step2_preview, step3_build
from citygen.gui import app as app_module
from citygen.gui import city_tabs as algo_module
from citygen.gui import extract_tab as extract_module
from citygen.gui import files, progress, server
from citygen.gui import form as form_module
from citygen.gui.bridge import Api
from citygen.settings import ALGO, BlockRegion


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

        self.assertEqual(boot["algo"], form_module.default_state())
        self.assertTrue(boot["extraction"]["worldReady"])
        self.assertTrue(all(area["chunks"] for area in boot["extraction"]["areas"].values()))

    def test_form_covers_every_grouped_knob_and_both_selectors(self):
        form = self.api.bootstrap()["form"]

        self.assertEqual([s["name"] for s in form["selectors"]], list(form_module.SELECTOR_OPTIONS))
        grouped = [field["name"] for group in form["groups"] for field in group["fields"]]
        self.assertEqual(grouped, [name for _code, names in form_module.GROUPS for name in names])

    def test_a_city_size_saved_as_its_old_label_falls_back_to_the_default(self):
        values = form_module.form_values({"FINE": "Small", "GAP_MIXED": "3"})

        self.assertEqual(values["FINE"], str(ALGO.fine))
        self.assertEqual(values["GAP_MIXED"], "3")


class ExtractTests(_ApiTestCase):
    def test_extraction_run_passes_the_source_world_and_its_areas(self):
        calls = []

        def fake_run(save, road_box, build_types, on_progress):
            calls.append((save, road_box, build_types))
            on_progress("scan_roads", 1, 1)
            on_progress("build_sheet", 1, 1)

        with mock.patch.object(step1_extract, "run", side_effect=fake_run):
            self.assertEqual(self.api.run_extract(), {})

        save, road_box, build_types = calls[0]
        self.assertEqual(save, extract_module.default_extraction_tab_config()["world_path"])
        self.assertIsInstance(road_box, BlockRegion)
        self.assertEqual([region.build_type for region in build_types], [1, 2])
        self.assertEqual(self.event_names()[0], "progress")
        self.assertEqual(self.event_names()[-2:], ["done", "finished"])

    def test_each_rendered_piece_is_shown_as_it_lands(self):
        with tempfile.TemporaryDirectory() as renders:
            def fake_run(_save, _road_box, _build_types, on_progress):
                Path(renders, "07_small_1x1_I.png").write_bytes(b"png")
                on_progress("road_sheet", 1, 3, "07_small_1x1_I")
                on_progress("road_sheet", 3, 3)

            with (
                mock.patch.object(extract_module, "ROADS_RENDERS", renders),
                mock.patch.object(step1_extract, "run", side_effect=fake_run),
            ):
                self.api.run_extract()

        pieces = [payload for event, payload in self.events if event == "piece"]
        self.assertEqual([(p["tab"], p["viewer"], p["index"]) for p in pieces], [("extract", "roads", 1)])

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

    def test_default_brings_back_the_bundled_world_and_its_areas(self):
        self.picked = "C:/mc/new-world"
        with (
            mock.patch.object(extract_module, "has_region_files", return_value=True),
            mock.patch.object(files, "clear_pipeline_artifacts") as clear,
        ):
            self.api.browse_world()
            answer = self.api.use_default_world()

        default = extract_module.default_extraction_tab_config()
        self.assertTrue(answer["changed"])
        self.assertEqual(answer["extraction"]["worldPath"], default["world_path"])
        self.assertTrue(all(area["chunks"] for area in answer["extraction"]["areas"].values()))
        self.assertEqual(clear.call_count, 2)   # the browse, then the default

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
            mock.patch.object(render_topdown, "cached_topdown_preview", return_value=(png, meta)),
            mock.patch.object(extract_module, "image", return_value={"src": "/files/world_preview/x.png?v=1"}),
        ):
            self.assertEqual(self.api.load_world_map(), {})

        self.assertEqual(self.last("worldMap"), {"src": "/files/world_preview/x.png?v=1", "meta": meta})

    def test_the_map_so_far_says_how_far_down_it_is_drawn(self):
        meta = {"x0": 0, "x1": 63, "z0": 0, "z1": 63, "step": 1}

        def fake_cached(save_path, *, on_progress, on_partial):
            on_progress(1, 4)
            on_partial(Path("partial.png"), meta)
            return Path("map.png"), meta

        with (
            mock.patch.object(render_topdown, "cached_topdown_preview", side_effect=fake_cached),
            mock.patch.object(extract_module, "image", return_value={"src": "/files/x.png?v=1"}),
        ):
            self.api.load_world_map()

        partial = [payload for event, payload in self.events if event == "worldMap" and payload.get("partial")]
        self.assertEqual(partial[0]["drawn"], 0.25)

    def test_extract_progress_reaches_each_step_end_without_creeping_past_it(self):
        value, soft_target, _detail = progress.bar("extract", "road_sheet", 4, 4)
        next_value, _soft, _detail = progress.bar("extract", "scan_builds", 0, 1)

        self.assertEqual(value, next_value)
        self.assertIsNone(soft_target)


class PreviewTests(_ApiTestCase):
    def test_preview_run_passes_a_fresh_seed_and_the_algo(self):
        calls = {}

        def fake_preview(seed, algo, on_progress):
            calls.update(seed=seed, algo=algo)
            on_progress("city_layout", 2, 2)

        state = form_module.default_state()
        with mock.patch.object(step2_preview, "run", side_effect=fake_preview):
            answer = self.api.run_preview(state)

        self.assertEqual(calls["algo"], ALGO)
        self.assertNotEqual(str(calls["seed"]), state["seed"])
        self.assertEqual(answer["state"]["seed"], str(calls["seed"]))
        self.assertEqual(self.saved[-1]["algo"]["seed"], str(calls["seed"]))
        self.assertEqual(self.event_names(), ["progress", "progress", "done", "finished"])
        self.assertEqual(set(self.last("done")["images"]), {"grid", "city"})

    def test_the_road_layout_shows_as_soon_as_its_step_is_done(self):
        def fake_preview(_seed, _algo, on_progress):
            on_progress("road_layout", 1, 1)
            on_progress("city_layout", 2, 2)

        with mock.patch.object(step2_preview, "run", side_effect=fake_preview):
            self.api.run_preview(form_module.default_state())

        self.assertEqual(self.event_names(), ["progress", "progress", "partial", "progress", "done", "finished"])
        self.assertEqual(list(self.last("partial")["images"]), ["grid"])

    def test_invalid_config_returns_the_error_without_running(self):
        state = form_module.default_state()
        state["algo"]["GAP_BIG"] = "lots"
        with mock.patch.object(step2_preview, "run") as run:
            answer = self.api.run_preview(state)

        run.assert_not_called()
        self.assertEqual(answer["error"], {"code": "invalid_config", "detail": "GAP_BIG"})
        self.assertEqual(self.events, [])

    def test_a_failed_run_reports_and_still_finishes(self):
        with mock.patch.object(step2_preview, "run", side_effect=RuntimeError("no roads")):
            self.api.run_preview(form_module.default_state())

        self.assertEqual(self.event_names(), ["progress", "failed", "finished"])
        self.assertEqual(self.last("failed")["detail"], "no roads")

    def test_reset_saves_and_returns_the_defaults(self):
        state = self.api.reset_algo()

        self.assertEqual(state, form_module.default_state())
        self.assertEqual(self.saved[-1]["algo"], state)


class BuildTests(_ApiTestCase):
    saved_config = {"extraction": {**extract_module.default_extraction_tab_config(), "world_path": "C:/mc/source-world"}}

    def test_build_run_exports_city_using_the_selected_source_world(self):
        calls = []

        def fake_build(seed, algo, save, on_progress):
            calls.append((seed, algo, save))
            on_progress("construct", 5, 8, "Composing voxel grid")
            on_progress("world", 1, 1)

        state = {**form_module.default_state(), "seed": "9"}
        with mock.patch.object(step3_build, "run", side_effect=fake_build):
            self.assertEqual(self.api.run_build(state), {})

        self.assertEqual(calls, [(9, ALGO, "C:/mc/source-world")])
        details = [payload.get("detail") for event, payload in self.events if event == "progress"]
        self.assertIn("Composing voxel grid", details)
        self.assertEqual(self.event_names()[-2:], ["done", "finished"])


class BuildBlueprintTests(_ApiTestCase):
    def test_the_previewed_city_stands_in_until_the_render(self):
        state = {**form_module.default_state(), "seed": "9"}
        with (
            mock.patch.object(step3_build, "run"),
            mock.patch.object(algo_module, "image", return_value={"src": "/files/03_preview/city/seed_9.png?v=1"}),
        ):
            self.api.run_build(state)

        partial = self.last("partial")
        self.assertEqual(partial["tab"], "build")
        self.assertTrue(partial["images"]["city"]["blueprint"])

    def test_no_blueprint_without_a_preview_of_this_seed(self):
        state = {**form_module.default_state(), "seed": "9"}
        with (
            mock.patch.object(step3_build, "run"),
            mock.patch.object(algo_module, "image", return_value={"missing": "seed_9.png"}),
        ):
            self.api.run_build(state)

        self.assertNotIn("partial", self.event_names())


class WarmUpTests(unittest.TestCase):
    def test_launch_warms_up_the_isometric_renderer(self):
        # The warm-up swallows every error, so a stale import would only show as a slow first extraction.
        with mock.patch("citygen.render_isometric.warm_up") as warm_up:
            app_module._warm_up_renderer()

        warm_up.assert_called_once()


class ProgressTests(unittest.TestCase):
    """Progress weights are hand-tuned, one per step a run reports."""

    def test_construct_has_a_weight_per_step(self):
        self.assertEqual(len(progress.CONSTRUCT_WEIGHTS), len(step3_build.STEPS))

    def test_run_bar_segments_span_every_weight_once(self):
        for tab, segments in progress.SEGMENTS.items():
            self.assertEqual(sum(count for _code, count in segments), len(progress.WEIGHTS[tab]))

    def test_run_bar_segments_tile_the_whole_bar(self):
        for spans in progress.run_segments().values():
            self.assertEqual(spans[0]["start"], 0)
            self.assertAlmostEqual(spans[-1]["end"], 100)
            for before, after in zip(spans, spans[1:]):
                self.assertEqual(before["end"], after["start"])

    def test_build_progress_names_only_the_construction_steps(self):
        _value, _soft, detail = progress.bar("build", "construct", 5, 8, "Composing voxel grid")
        _value, _soft, render_detail = progress.bar("build", "render", 0, 1, "done")

        self.assertEqual(detail, "Composing voxel grid")
        self.assertIsNone(render_detail)

    def test_preview_progress_creeps_toward_the_next_item(self):
        start, _soft, _detail = progress.bar("preview", "city_layout", 0, 2)
        value, soft_target, detail = progress.bar("preview", "city_layout", 1, 2)
        end, _soft, _detail = progress.bar("preview", "city_layout", 2, 2)

        self.assertAlmostEqual(value, (start + end) / 2)
        self.assertGreater(soft_target, value)
        self.assertEqual(detail, progress.PREVIEW_DETAILS["city_layout"])


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
        status, headers, body = self.get("/icons/extract.svg")

        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "image/svg+xml")
        self.assertTrue(body.startswith(b"<svg"))

    def test_the_page_is_served_with_its_content_types(self):
        for path, content_type in (("/", "text/html"), ("/app.js", "text/javascript"), ("/app.css", "text/css")):
            status, headers, _body = self.get(path)
            self.assertEqual(status, "200 OK")
            self.assertEqual(headers["Content-Type"], content_type)


class WorldPreviewTests(unittest.TestCase):
    def test_each_picture_so_far_is_its_own_file_and_a_new_render_clears_the_last(self):
        from PIL import Image

        meta = {"x0": 0, "x1": 15, "z0": 0, "z1": 15, "step": 1}

        def render(cache, mtime, pictures):
            def fake_render(save_path, *, on_progress=None, on_partial=None):
                for _ in range(pictures):
                    on_partial(Image.new("RGB", (16, 16)), meta)
                return Image.new("RGB", (16, 16)), meta

            reported = []
            with (
                mock.patch.object(render_topdown, "WORLD_PREVIEW_CACHE", cache),
                mock.patch.object(render_topdown, "render_topdown_preview", side_effect=fake_render),
                mock.patch.object(render_topdown, "_preview_region_mtime", return_value=mtime),
            ):
                png, _meta = render_topdown.cached_topdown_preview("C:/mc/world", on_partial=lambda p, m: reported.append(p))
            return png, reported

        with tempfile.TemporaryDirectory() as cache:
            png, first = render(cache, 1.0, pictures=2)
            self.assertEqual(len(set(first)), 2)                      # two pictures, two files
            self.assertTrue(all(path.exists() for path in first))     # kept, for a page still fetching them
            self.assertTrue(png.exists())

            _png, second = render(cache, 2.0, pictures=1)             # the world changed: drawn again
            self.assertEqual(second, first[:1])
            self.assertFalse(first[1].exists())                       # the last render's other picture is gone

    def test_chunk_span_counts_partial_chunks_and_negative_coordinates(self):
        self.assertEqual(extract_module.chunk_span((-1, 0, 0), (16, 0, 15)), [3, 1])


class PageMirrorTests(unittest.TestCase):
    """What Python and the page each hold a copy of, kept in step."""

    def read(self, name):
        return (server.STATIC / name).read_text(encoding="utf-8")

    def test_text_js_words_every_code_python_sends(self):
        text = self.read("text.js")
        codes = (
            form_module.KNOBS
            + [code for code, _names in form_module.GROUPS]
            + [code for segments in progress.SEGMENTS.values() for code, _count in segments]
        )
        for code in codes:
            self.assertRegex(text, rf"\b{code}:", code)
        for name, options in form_module.SELECTOR_OPTIONS.items():
            words = re.search(rf"{name}: \{{([^}}]*)\}}", text).group(1)
            self.assertEqual(re.findall(r"(\d+):", words), list(options), name)

    def test_the_page_loads_every_script_and_stylesheet_it_has(self):
        page = self.read("index.html")
        linked = re.findall(r'<(?:script src|link rel="stylesheet" href)="([^"]+)"', page)
        present = sorted(
            path.relative_to(server.STATIC).as_posix() for path in server.STATIC.rglob("*") if path.suffix in (".js", ".css")
        )
        self.assertEqual(sorted(linked), present)

    def test_the_region_map_snaps_to_the_same_chunks(self):
        self.assertIn(f"const CHUNK_SIZE = {extract_module.CHUNK_SIZE};", self.read("region/region.js"))

    def test_the_window_reads_its_colours_from_the_page(self):
        for color in app_module.page_colors("app-bg", "sky", "sky-text"):
            self.assertRegex(color, r"^#[0-9a-fA-F]{6}$")


if __name__ == "__main__":
    unittest.main()
