"""Pipeline orchestration: stage services and the roads extraction stage."""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
import numpy as np
from PIL import Image

from pipeline import runtime
from pipeline import services
from pipeline.stages import PIPELINE_STAGE_MODULES, RELOAD_ORDER, stage_module
from engine.schematic.transform import Tile

ROOT_DIR = Path(__file__).resolve().parents[1]
BUILDS_EXTRACT = stage_module("builds_extract")
BUILDS_RENDER = stage_module("builds_render")
ROADS_RENDER = stage_module("roads_render")


# --- stage services -------------------------------------------------------

def test_reload_order_stays_in_sync_with_stage_registry():
    assert tuple(RELOAD_ORDER[-len(PIPELINE_STAGE_MODULES):]) == PIPELINE_STAGE_MODULES


@pytest.mark.parametrize("module_name", PIPELINE_STAGE_MODULES)
def test_pipeline_stage_scripts_bootstrap_without_pythonpath(module_name):
    script = ROOT_DIR / "src" / Path(*module_name.split(".")).with_suffix(".py")
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_configured_environment_restores_requested_keys(monkeypatch):
    monkeypatch.setattr(runtime, "reload_pipeline_modules", lambda: None)
    monkeypatch.setenv("MC_CITY_FINE", "80")
    monkeypatch.delenv("MC_CITY_GAP_BIG", raising=False)

    with runtime.configured_environment({"MC_CITY_FINE": "60", "MC_CITY_GAP_BIG": "7"}):
        assert os.environ["MC_CITY_FINE"] == "60"
        assert os.environ["MC_CITY_GAP_BIG"] == "7"

    assert os.environ["MC_CITY_FINE"] == "80"
    assert "MC_CITY_GAP_BIG" not in os.environ


def test_run_grid_simulation_stage_coerces_numeric_arguments(monkeypatch):
    calls = {}

    @contextmanager
    def fake_environment(env_overrides):
        calls["env_overrides"] = env_overrides
        yield

    def fake_run(**kwargs):
        calls["kwargs"] = kwargs
        return {"stage": "grid"}

    def fake_import_module(module_name):
        calls["module_name"] = module_name
        return SimpleNamespace(run=fake_run)

    monkeypatch.setattr(services, "configured_environment", fake_environment)
    monkeypatch.setattr(services.importlib, "import_module", fake_import_module)

    result = services.run_grid_simulation_stage("7", "3", env_overrides={"MC_CITY_FINE": "3"}, logger="logger")

    assert calls["env_overrides"] == {"MC_CITY_FINE": "3"}
    assert calls["module_name"] == services.GRID_SIMULATION
    assert calls["kwargs"] == {"seed": 7, "fine": 3, "logger": "logger"}
    assert result["stage"] == "grid"


def test_run_build_extraction_pipeline_tags_progress_with_stage_modules(monkeypatch):
    calls = []
    progress_events = []

    @contextmanager
    def fake_environment(_env_overrides):
        yield

    def fake_import_module(module_name):
        def fake_run(**kwargs):
            calls.append((module_name, kwargs["logger"]))
            progress = kwargs.get("progress")
            if progress is not None:
                if module_name == BUILDS_EXTRACT:
                    progress(1, 4, "Scanning")
                else:
                    progress(4, 4, "Rendering sheet")
            return module_name

        return SimpleNamespace(run=fake_run)

    monkeypatch.setattr(services, "configured_environment", fake_environment)
    monkeypatch.setattr(services.importlib, "import_module", fake_import_module)

    result = services.run_build_extraction_pipeline(
        env_overrides={"MC_CITY_SAVE": "world"},
        logger="logger",
        progress=lambda stage, completed, total, label: progress_events.append((stage, completed, total, label)),
    )

    assert calls == [(BUILDS_EXTRACT, "logger"), (BUILDS_RENDER, "logger")]
    assert progress_events == [
        (BUILDS_EXTRACT, 1, 4, "Scanning"),
        (BUILDS_RENDER, 4, 4, "Rendering sheet"),
    ]
    assert result == {"extract": BUILDS_EXTRACT, "render": BUILDS_RENDER}


# --- roads extraction stage ----------------------------------------------

roads_extract = importlib.import_module("pipeline.01_roads.extract")
builds_render = importlib.import_module("pipeline.02_builds.render")
roads_render = importlib.import_module("pipeline.01_roads.render")
city_construct = importlib.import_module("pipeline.04_city.construct")


def _component(boundary, cuboid, *, ground_y=None):
    if ground_y is None:
        ground_y = cuboid[2]
    return types.SimpleNamespace(boundary=boundary, cuboids=[cuboid], ground_y=ground_y)


class RoadsExtractTests(unittest.TestCase):
    def test_run_removes_stale_schems_before_extracting(self):
        with tempfile.TemporaryDirectory() as tempdir:
            out_dir = Path(tempdir)
            stale = out_dir / "stale.schem"
            stale.write_text("old", encoding="utf-8")

            component = _component((0, 2, 0, 2), (0, 2, 65, 70, 0, 2), ground_y=67)
            cells = [[["minecraft:stone"]]]

            with mock.patch.object(roads_extract, "OUT", str(out_dir)), \
                 mock.patch.object(roads_extract, "get_world", return_value=mock.Mock()), \
                 mock.patch.object(roads_extract, "ground_shift", return_value=0), \
                 mock.patch.object(roads_extract, "read_names", return_value=[(1, 1, "fresh")]), \
                 mock.patch.object(roads_extract, "detect_assets", return_value=([component], [])), \
                 mock.patch.object(roads_extract, "extract_cuboid", return_value=(cells, [])), \
                 mock.patch.object(roads_extract, "write_sponge_schem_cells") as write_schem:
                result = roads_extract.run()

            self.assertFalse(stale.exists())
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["items"], ["fresh"])
            write_schem.assert_called_once()
            self.assertEqual(write_schem.call_args.args[1], str(out_dir / "fresh.schem"))
            self.assertEqual(write_schem.call_args.kwargs["offset"], (0, -2, 0))

    def test_run_raises_when_no_components_were_found(self):
        with tempfile.TemporaryDirectory() as tempdir:
            out_dir = Path(tempdir)
            stale = out_dir / "stale.schem"
            stale.write_text("old", encoding="utf-8")

            with mock.patch.object(roads_extract, "OUT", str(out_dir)), \
                 mock.patch.object(roads_extract, "get_world", return_value=mock.Mock()), \
                 mock.patch.object(roads_extract, "ground_shift", return_value=0), \
                 mock.patch.object(roads_extract, "read_names", return_value=[]), \
                 mock.patch.object(roads_extract, "detect_assets", return_value=([], [])):
                with self.assertRaisesRegex(RuntimeError, "found no assets"):
                    roads_extract.run()

            self.assertFalse(stale.exists())


class ContactRenderTests(unittest.TestCase):
    def test_builds_render_uses_saved_png_paths_for_contact_sheet_and_reports_contact_progress(self):
        with tempfile.TemporaryDirectory() as tempdir:
            out_dir = Path(tempdir)
            catalog_path = out_dir / "buildings.json"
            catalog_path.write_text(
                '{"001": {"type": 1}, "002": {"type": 1}}',
                encoding="utf-8",
            )
            progress_events = []

            real_write_contact = importlib.import_module("engine.render.isometric").write_contact

            def checking_write_contact(images, out, **kwargs):
                assert all(isinstance(source, (str, os.PathLike)) for _key, source in images)
                return real_write_contact(images, out, **kwargs)

            with mock.patch.object(builds_render, "CATALOG", str(catalog_path)), \
                 mock.patch.object(builds_render, "SCHEM", str(out_dir)), \
                 mock.patch.object(builds_render, "BUILDS_PROD", str(out_dir)), \
                 mock.patch.object(builds_render, "assemble", return_value=[[["minecraft:stone"]]]), \
                 mock.patch.object(builds_render, "render_cells_visible_iso", return_value=Image.new("RGBA", (16, 16))), \
                 mock.patch.object(builds_render, "write_contact", side_effect=checking_write_contact):
                result = builds_render.run(
                    progress=lambda completed, total, label: progress_events.append((completed, total, label)),
                )

            assert result["count"] == 2
            assert (out_dir / "001.png").exists()
            assert (out_dir / "002.png").exists()
            assert (out_dir / "_contact_sheet.png").exists()
            assert progress_events == [
                (1, 5, "001"),
                (2, 5, "002"),
                (3, 5, "Rendering build contact sheet..."),
                (4, 5, "Rendering build contact sheet..."),
                (5, 5, "Rendered build contact sheet."),
            ]

    def test_roads_render_uses_saved_png_paths_for_contact_sheet_and_reports_contact_progress(self):
        with tempfile.TemporaryDirectory() as tempdir:
            out_dir = Path(tempdir)
            (out_dir / "a.schem").write_text("stub", encoding="utf-8")
            (out_dir / "b.schem").write_text("stub", encoding="utf-8")
            progress_events = []

            real_write_contact = importlib.import_module("engine.render.isometric").write_contact

            def checking_write_contact(images, out, **kwargs):
                assert all(isinstance(source, (str, os.PathLike)) for _key, source in images)
                return real_write_contact(images, out, **kwargs)

            with mock.patch.object(roads_render, "SCHEM", str(out_dir)), \
                 mock.patch.object(roads_render, "ROADS_PROD", str(out_dir)), \
                 mock.patch.object(roads_render, "decode_schem_cells", return_value=[[["minecraft:stone"]]]), \
                 mock.patch.object(roads_render, "render_cells_visible_iso", return_value=Image.new("RGBA", (16, 16))), \
                 mock.patch.object(roads_render, "write_contact", side_effect=checking_write_contact):
                result = roads_render.run(
                    progress=lambda completed, total, label: progress_events.append((completed, total, label)),
                )

            assert result["count"] == 2
            assert (out_dir / "a.png").exists()
            assert (out_dir / "b.png").exists()
            assert (out_dir / "_contact_sheet.png").exists()
            assert progress_events == [
                (1, 5, "a"),
                (2, 5, "b"),
                (3, 5, "Rendering road contact sheet..."),
                (4, 5, "Rendering road contact sheet..."),
                (5, 5, "Rendered road contact sheet."),
            ]


def test_run_city_construct_stage_requires_integer_seed():
    with pytest.raises(ValueError, match="Seed must be an integer."):
        services.run_city_construct_stage("bad", "2")  # coercion guard shared by all stage services


def test_city_ground_fill_asset_uses_shared_marker_ground_plane():
    grid = np.zeros((6, 12, 12), dtype=np.int16)
    palette = {"minecraft:air": 0}
    build_mask = np.zeros((12, 12), dtype=bool)
    size = SimpleNamespace(fine=1)
    tile = Tile(
        width=1,
        height=1,
        length=1,
        cells=[[["minecraft:moss_block"]]],
        ground_offset=0,
    )

    city_construct._place_ground_fill(
        grid,
        palette,
        build_mask,
        road_cells=set(),
        size=size,
        ground_y=3,
        ground_fill_tile=tile,
    )

    z0 = city_construct.PLAYER_ANCHOR_MARGIN
    z1 = z0 + city_construct.BLOCKS_PER_CELL
    x0 = city_construct.PLAYER_ANCHOR_MARGIN
    x1 = x0 + city_construct.BLOCKS_PER_CELL
    assert np.count_nonzero(grid[3, z0:z1, x0:x1]) == city_construct.BLOCKS_PER_CELL ** 2
    assert np.count_nonzero(grid[2, z0:z1, x0:x1]) == 0

    offset_tile = Tile(
        width=1,
        height=1,
        length=1,
        cells=[[["minecraft:oak_planks"]]],
        ground_offset=1,
    )
    city_construct._place_ground_fill(
        grid,
        palette,
        build_mask,
        road_cells=set(),
        size=size,
        ground_y=3,
        ground_fill_tile=offset_tile,
    )
    assert np.count_nonzero(grid[2, z0:z1, x0:x1]) == city_construct.BLOCKS_PER_CELL ** 2


def test_city_ground_fill_skips_cells_with_fill_props():
    grid = np.zeros((6, 12, 12), dtype=np.int16)
    palette = {"minecraft:air": 0}
    build_mask = np.zeros((12, 12), dtype=bool)
    size = SimpleNamespace(fine=1)
    tile = Tile(
        width=1,
        height=1,
        length=1,
        cells=[[["minecraft:dirt"]]],
        ground_offset=0,
    )

    city_construct._place_ground_fill(
        grid,
        palette,
        build_mask,
        road_cells=set(),
        size=size,
        ground_y=3,
        ground_fill_tile=tile,
        skip_cells={(0, 0)},
    )

    z0 = city_construct.PLAYER_ANCHOR_MARGIN
    z1 = z0 + city_construct.BLOCKS_PER_CELL
    x0 = city_construct.PLAYER_ANCHOR_MARGIN
    x1 = x0 + city_construct.BLOCKS_PER_CELL
    assert np.count_nonzero(grid[:, z0:z1, x0:x1]) == 0


if __name__ == "__main__":
    unittest.main()
