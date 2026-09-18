"""Pipeline orchestration: stage services and the roads extraction stage."""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
import numpy as np
from PIL import Image

from config.algo import CELL
from config.path import exported_world_name
from pipeline import services
from pipeline import stages
from pipeline.stages import PIPELINE_STAGE_COMMANDS, PIPELINE_STAGE_MODULES
from engine.schematic.transform import Tile
from engine.schematic import city as city_grid
from engine.world import marker_extract

ROOT_DIR = Path(__file__).resolve().parents[1]


# --- stage services -------------------------------------------------------


def _run_script_help(script, *args):
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, str(script), *args, "--help"],
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


@pytest.mark.parametrize("module_name", PIPELINE_STAGE_MODULES)
def test_pipeline_stage_script_bootstraps_without_pythonpath(module_name):
    script = ROOT_DIR / "src" / Path(*module_name.split(".")).with_suffix(".py")
    _run_script_help(script)


@pytest.mark.parametrize("stage_key", PIPELINE_STAGE_COMMANDS)
def test_pipeline_stage_subcommands_bootstrap_without_pythonpath(stage_key):
    script = ROOT_DIR / "src" / "pipeline" / "stages.py"
    _run_script_help(script, stage_key)


def test_world_export_uses_seeded_world_name_for_folder_and_level(monkeypatch, tmp_path):
    schem_dir = tmp_path / "schem"
    saves_dir = tmp_path / "saves"
    source = tmp_path / "source"
    schem_dir.mkdir()
    saves_dir.mkdir()
    source.mkdir()
    (schem_dir / "seed_12.schem").write_bytes(b"schem")
    calls = {}

    def fake_schem_to_world(schem, out, **kwargs):
        calls["schem"] = schem
        calls["out"] = out
        calls["kwargs"] = kwargs
        return {"chunks": 1, "regions": 1, "block_entities": 0, "out_dir": out}

    monkeypatch.setattr(world_export, "city_schem_path", lambda seed: str(schem_dir / f"seed_{seed}.schem"))
    monkeypatch.setattr(world_export, "exported_world_path", lambda seed: str(saves_dir / exported_world_name(seed)))
    monkeypatch.setattr(world_export, "SAVE", str(source))
    monkeypatch.setattr(world_export, "schem_to_world", fake_schem_to_world)

    result = world_export.run(seed=12)

    expected_out = str(saves_dir / "Minecraft CityGen World 12")
    assert result["output_path"] == expected_out
    assert calls["schem"] == str(schem_dir / "seed_12.schem")
    assert calls["out"] == expected_out
    assert calls["kwargs"]["world_name"] == "Minecraft CityGen World 12"


# --- roads extraction stage ----------------------------------------------

roads_extract = importlib.import_module("pipeline.01_roads.extract")
builds_extract = importlib.import_module("pipeline.02_builds.extract")
builds_render = importlib.import_module("pipeline.02_builds.render")
roads_render = importlib.import_module("pipeline.01_roads.render")
world_export = importlib.import_module("pipeline.05_world.export")


def _component(boundary, cuboid, *, ground_offset=0, emerald=(1, 64, 1)):
    return types.SimpleNamespace(
        boundary=boundary,
        cuboids=[cuboid],
        ground_offset=ground_offset,
        emerald=emerald,
    )


class RoadsExtractTests(unittest.TestCase):
    def test_run_removes_stale_schems_before_extracting(self):
        with tempfile.TemporaryDirectory() as tempdir:
            out_dir = Path(tempdir)
            stale = out_dir / "stale.schem"
            stale.write_text("old", encoding="utf-8")

            component = _component((0, 2, 0, 2), (0, 2, 65, 70, 0, 2), ground_offset=2)
            cells = [[["minecraft:stone"]]]

            with mock.patch.object(roads_extract, "ROADS_SCHEM", str(out_dir)), \
                 mock.patch.object(roads_extract, "open_world", return_value=mock.Mock()), \
                 mock.patch.object(roads_extract, "name_for", return_value="fresh"), \
                 mock.patch.object(roads_extract, "detect_marker_assets", return_value=([component], [])), \
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

            with mock.patch.object(roads_extract, "ROADS_SCHEM", str(out_dir)), \
                 mock.patch.object(roads_extract, "open_world", return_value=mock.Mock()), \
                 mock.patch.object(roads_extract, "detect_marker_assets", return_value=([], [])):
                with self.assertRaisesRegex(RuntimeError, "found no assets"):
                    roads_extract.run()

            self.assertFalse(stale.exists())


def test_build_stack_sign_reads_sign_one_block_above_emerald(monkeypatch):
    monkeypatch.setattr(
        marker_extract,
        "iter_signs",
        lambda _world, _xa, _xb, _za, _zb: [
            (4, 70, 8, "stack: 9"),
            (4, 71, 8, "stack: 2-5"),
        ],
    )
    assert builds_extract.stack_sign(object(), (4, 70, 8)) == [2, 5]


def test_road_name_reads_sign_one_block_above_emerald(monkeypatch):
    monkeypatch.setattr(
        marker_extract,
        "iter_signs",
        lambda _world, _xa, _xb, _za, _zb: [
            (4, 70, 8, "wrong"),
            (4, 71, 8, " 02_big _2x2 _I "),
        ],
    )
    assert roads_extract.name_for(object(), (4, 70, 8)) == "02_big_2x2_I"


def _checking_write_contact():
    """Patch the shared contact writer to assert it receives image paths, not images."""
    rendering = importlib.import_module("pipeline.rendering")
    real_write_contact = rendering.write_contact

    def checking_write_contact(images, out, **kwargs):
        assert all(isinstance(source, (str, os.PathLike)) for _key, source in images)
        return real_write_contact(images, out, **kwargs)

    return mock.patch.object(rendering, "write_contact", side_effect=checking_write_contact)


class ContactRenderTests(unittest.TestCase):
    def test_builds_render_writes_piece_images_and_contact_sheet(self):
        with tempfile.TemporaryDirectory() as tempdir:
            out_dir = Path(tempdir)
            catalog_path = out_dir / "buildings.json"
            catalog_path.write_text(
                '{"001": {"type": 1}, "002": {"type": 1}}',
                encoding="utf-8",
            )

            with mock.patch.object(builds_render, "read_catalog", return_value={"001": {"type": 1}, "002": {"type": 1}}), \
                 mock.patch.object(builds_render, "BUILDS_RENDERS", str(out_dir)), \
                 mock.patch.object(builds_render, "BUILDS_CONTACT_SHEET", str(out_dir / "_contact_sheet.png")), \
                 mock.patch.object(builds_render, "BUILDS_GIF", str(out_dir / "buildings.gif")), \
                 mock.patch.object(builds_render, "assemble", return_value=Tile(1, 1, 1, [[["minecraft:stone"]]])), \
                 mock.patch.object(builds_render, "render_cells_visible_iso", return_value=Image.new("RGBA", (16, 16))), \
                 _checking_write_contact():
                result = builds_render.run()

            assert result["count"] == 2
            assert (out_dir / "001.png").exists()
            assert (out_dir / "002.png").exists()
            assert (out_dir / "_contact_sheet.png").exists()
            assert result["gif"] == str(out_dir / "buildings.gif")
            assert (out_dir / "buildings.gif").exists()

    def test_roads_render_writes_piece_images_and_contact_sheet(self):
        with tempfile.TemporaryDirectory() as tempdir:
            out_dir = Path(tempdir)
            (out_dir / "a.schem").write_text("stub", encoding="utf-8")
            (out_dir / "b.schem").write_text("stub", encoding="utf-8")

            with mock.patch.object(roads_render, "ROADS_SCHEM", str(out_dir)), \
                 mock.patch.object(roads_render, "ROADS_RENDERS", str(out_dir)), \
                 mock.patch.object(roads_render, "ROADS_CONTACT_SHEET", str(out_dir / "_contact_sheet.png")), \
                 mock.patch.object(roads_render, "decode_schem_cells", return_value=[[["minecraft:stone"]]]), \
                 mock.patch.object(roads_render, "render_cells_visible_iso", return_value=Image.new("RGBA", (16, 16))), \
                 _checking_write_contact():
                result = roads_render.run()

            assert result["count"] == 2
            assert (out_dir / "a.png").exists()
            assert (out_dir / "b.png").exists()
            assert (out_dir / "_contact_sheet.png").exists()


def test_run_stage_requires_integer_seed():
    with pytest.raises(ValueError, match="Seed must be an integer."):
        services.run_stage("city", seed="bad", fine="2")


def test_run_stage_forwards_params_and_tags_progress_by_step_module(monkeypatch):
    calls = []

    def fake_module(module):
        def run(*, logger, progress, **kwargs):
            calls.append((module, kwargs))
            progress(1, 1, "done")
            return module

        return types.SimpleNamespace(run=run)

    monkeypatch.setattr(stages.importlib, "import_module", fake_module)
    ticks = []

    results = stages.run_stage("city", seed=3, progress=lambda *tick: ticks.append(tick))

    assert calls == [(stages.CITY_CONSTRUCT, {"seed": 3}), (stages.CITY_RENDER, {"seed": 3})]
    assert results == {"construct": stages.CITY_CONSTRUCT, "render": stages.CITY_RENDER}
    assert ticks == [(stages.CITY_CONSTRUCT, 1, 1, "done"), (stages.CITY_RENDER, 1, 1, "done")]


def test_run_stage_rejects_parameters_no_step_accepts():
    with pytest.raises(TypeError, match="unexpected parameters"):
        stages.run_stage("roads", seed=1)


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

    city_grid.place_ground_fill(
        grid,
        palette,
        build_mask,
        road_cells=set(),
        size=size,
        ground_y=3,
        ground_fill_tile=tile,
    )

    z0 = city_grid.PLAYER_ANCHOR_MARGIN
    z1 = z0 + CELL
    x0 = city_grid.PLAYER_ANCHOR_MARGIN
    x1 = x0 + CELL
    assert np.count_nonzero(grid[3, z0:z1, x0:x1]) == CELL ** 2
    assert np.count_nonzero(grid[2, z0:z1, x0:x1]) == 0

    offset_tile = Tile(
        width=1,
        height=1,
        length=1,
        cells=[[["minecraft:oak_planks"]]],
        ground_offset=1,
    )
    city_grid.place_ground_fill(
        grid,
        palette,
        build_mask,
        road_cells=set(),
        size=size,
        ground_y=3,
        ground_fill_tile=offset_tile,
    )
    assert np.count_nonzero(grid[2, z0:z1, x0:x1]) == CELL ** 2


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

    city_grid.place_ground_fill(
        grid,
        palette,
        build_mask,
        road_cells=set(),
        size=size,
        ground_y=3,
        ground_fill_tile=tile,
        skip_cells={(0, 0)},
    )

    z0 = city_grid.PLAYER_ANCHOR_MARGIN
    z1 = z0 + CELL
    x0 = city_grid.PLAYER_ANCHOR_MARGIN
    x1 = x0 + CELL
    assert np.count_nonzero(grid[:, z0:z1, x0:x1]) == 0


if __name__ == "__main__":
    unittest.main()
