"""Pipeline orchestration: stage services and the roads extraction stage."""
from __future__ import annotations

import importlib
import tempfile
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from pipeline import services
from pipeline.stages import PIPELINE_STAGE_MODULES, RELOAD_ORDER, stage_module

BUILDS_EXTRACT = stage_module("builds_extract")
BUILDS_RENDER = stage_module("builds_render")


# --- stage services -------------------------------------------------------

def test_reload_order_stays_in_sync_with_stage_registry():
    assert tuple(RELOAD_ORDER[-len(PIPELINE_STAGE_MODULES):]) == PIPELINE_STAGE_MODULES


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


def test_run_city_construct_stage_requires_integer_seed():
    with pytest.raises(ValueError, match="Seed must be an integer."):
        services.run_city_construct_stage("bad", "2")  # coercion guard shared by all stage services


if __name__ == "__main__":
    unittest.main()
