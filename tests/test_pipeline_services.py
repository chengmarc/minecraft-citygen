from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from pipeline import services
from pipeline.stages import PIPELINE_STAGE_MODULES, RELOAD_ORDER, stage_module

BUILDS_EXTRACT = stage_module("builds_extract")
BUILDS_RENDER = stage_module("builds_render")


def test_reload_order_stays_in_sync_with_stage_registry():
    assert tuple(RELOAD_ORDER[-len(PIPELINE_STAGE_MODULES) :]) == PIPELINE_STAGE_MODULES


def test_run_grid_simulation_stage_coerces_numeric_arguments(monkeypatch):
    calls = {}

    @contextmanager
    def fake_environment(env_overrides):
        calls["env_overrides"] = env_overrides
        yield

    def fake_run(**kwargs):
        calls["kwargs"] = kwargs
        return {"stage": "grid", "kwargs": kwargs}

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


def test_run_build_extraction_pipeline_adapts_progress_labels(monkeypatch):
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

    assert calls == [
        (BUILDS_EXTRACT, "logger"),
        (BUILDS_RENDER, "logger"),
    ]
    assert progress_events == [
        ("Extracting", 1, 4, "Scanning"),
        ("Rendering", 4, 4, "Rendering sheet"),
    ]
    assert result == {
        "extract": BUILDS_EXTRACT,
        "render": BUILDS_RENDER,
    }


def test_run_city_construct_stage_requires_integer_seed_and_fine():
    with pytest.raises(ValueError, match="Seed must be an integer."):
        services.run_city_construct_stage("bad", "2")
