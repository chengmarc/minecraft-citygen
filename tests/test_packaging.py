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


def test_msix_version_appends_the_zero_revision_the_store_requires():
    build = load_build_script()

    assert build.msix_version("1.2.0") == "1.2.0.0"


def test_msix_manifest_renders_to_valid_xml_with_the_store_identity(monkeypatch):
    import xml.etree.ElementTree as ET

    build = load_build_script()
    monkeypatch.setattr(build, "MSIX_IDENTITY_NAME", "12345Publisher.MinecraftCityGen")
    monkeypatch.setattr(build, "MSIX_PUBLISHER", "CN=00000000-0000-0000-0000-000000000000")
    monkeypatch.setattr(build, "MSIX_PUBLISHER_DISPLAY_NAME", "Publisher")

    root = ET.fromstring(build.render_msix_manifest("1.2.0"))

    ns = {"m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10"}
    identity = root.find("m:Identity", ns)
    assert identity.get("Name") == "12345Publisher.MinecraftCityGen"
    assert identity.get("Version") == "1.2.0.0"
    assert root.find("m:Applications/m:Application", ns).get("Executable") == f"{build.APP_NAME}.exe"
    for logo in build.MSIX_LOGOS:
        assert f"Assets\{logo}" in ET.tostring(root, encoding="unicode")
