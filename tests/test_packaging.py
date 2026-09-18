"""Windows release packaging command construction."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def load_build_script():
    script = Path(__file__).resolve().parents[1] / "packaging" / "build_windows_release.py"
    spec = importlib.util.spec_from_file_location("build_windows_release", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_pyinstaller_command_includes_numbered_pipeline_stage_modules():
    build = load_build_script()

    command = build.base_pyinstaller_command(onefile=False, icon_path=None)

    for module_name in build.PIPELINE_STAGE_HIDDEN_IMPORTS:
        assert ["--hidden-import", module_name] in [
            command[i:i + 2]
            for i in range(len(command) - 1)
        ]


def test_pyinstaller_hidden_imports_mirror_the_stage_registry():
    from pipeline.stages import STAGES

    stage_modules = {step.module for steps in STAGES.values() for step in steps}
    assert set(load_build_script().PIPELINE_STAGE_HIDDEN_IMPORTS) == stage_modules
