"""Developer tooling: the render-colour extractor and the Windows release build."""
import importlib.util
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from PIL import Image

ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT_DIR / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = _load_module("update_render_colors", "tools/update_render_colors.py")
build_windows_release = _load_module("build_windows_release", "packaging/build_windows_release.py")

MinecraftTopColorExtractor = MODULE.MinecraftTopColorExtractor


# --- update_render_colors -------------------------------------------------

def test_write_csv_includes_expected_header(tmp_path):
    output = tmp_path / "color_render.csv"
    MODULE.write_csv([("minecraft:stone", 1, 2, 3)], output)
    assert output.read_text(encoding="utf-8").splitlines() == [
        "block_name,r,g,b",
        "minecraft:stone,1,2,3",
    ]


def test_resolve_version_metadata_defaults_to_latest_release(monkeypatch):
    manifest = {
        "latest": {"release": "1.2.3"},
        "versions": [
            {"id": "1.2.3", "url": "https://example.invalid/1.2.3.json"},
            {"id": "1.2.2", "url": "https://example.invalid/1.2.2.json"},
        ],
    }
    monkeypatch.setattr(MODULE, "load_json_url", lambda url: manifest)

    version_id, metadata = MODULE.resolve_version_metadata(None)
    assert version_id == "1.2.3"
    assert metadata["url"] == "https://example.invalid/1.2.3.json"


def test_download_client_jar_reuses_matching_cached_file(monkeypatch, tmp_path):
    version_id = "1.2.3"
    jar_path = tmp_path / f"minecraft-client-{version_id}.jar"
    jar_bytes = b"cached-jar"
    jar_path.write_bytes(jar_bytes)
    expected_sha1 = MODULE.hashlib.sha1(jar_bytes).hexdigest()

    monkeypatch.setattr(MODULE, "TOOLS_DIR", tmp_path)
    monkeypatch.setattr(
        MODULE, "resolve_version_metadata",
        lambda version: (version_id, {"url": "https://example.invalid/version.json"}),
    )
    monkeypatch.setattr(
        MODULE, "load_json_url",
        lambda url: {"downloads": {"client": {"url": "https://example.invalid/client.jar", "sha1": expected_sha1}}},
    )

    def unexpected_urlopen(*args, **kwargs):
        raise AssertionError("cache hit should not download")

    monkeypatch.setattr(MODULE.urllib.request, "urlopen", unexpected_urlopen)

    actual_version, actual_path = MODULE.download_client_jar(version_id)
    assert actual_version == version_id
    assert actual_path == jar_path


def test_average_block_color_tints_only_faces_with_tintindex(monkeypatch):
    extractor = object.__new__(MinecraftTopColorExtractor)
    full_cube_top = MODULE.Face(
        texture_path="leaf_texture", x1=0, x2=16, z1=0, z2=16, y=16,
        uv=(0, 0, 16, 16), rotation=0, order=0, tinted=True,
    )
    monkeypatch.setattr(extractor, "collect_faces", lambda block_name: [full_cube_top])
    solid = Image.new("RGBA", (16, 16), (150, 150, 150, 255))
    monkeypatch.setattr(extractor, "load_texture", lambda texture_path: (solid, solid.size))

    expected = MODULE._apply_tint((150, 150, 150), MODULE.FOLIAGE_TINT)
    assert extractor.average_block_color("oak_leaves") == expected

    # An identical block whose face carries no tintindex is left untinted.
    plain_top = MODULE.Face(
        texture_path="leaf_texture", x1=0, x2=16, z1=0, z2=16, y=16,
        uv=(0, 0, 16, 16), rotation=0, order=0, tinted=False,
    )
    monkeypatch.setattr(extractor, "collect_faces", lambda block_name: [plain_top])
    assert extractor.average_block_color("oak_leaves") == (150, 150, 150)


def test_apply_renamed_aliases_adds_old_ids_from_current_colours():
    rows = [
        ("minecraft:stone", 1, 2, 3),
        ("minecraft:short_grass", 83, 107, 51),
        ("minecraft:iron_chain", 51, 58, 74),
    ]
    by_name = {name: (r, g, b) for name, r, g, b in MODULE.apply_renamed_aliases(rows)}
    # Old ids inherit the current block's colour, and the current ids are still present.
    assert by_name["minecraft:grass"] == (83, 107, 51)
    assert by_name["minecraft:chain"] == (51, 58, 74)
    assert by_name["minecraft:short_grass"] == (83, 107, 51)


def test_average_texture_color_ignores_transparent_pixels():
    extractor = object.__new__(MinecraftTopColorExtractor)
    image = Image.new("RGBA", (2, 1))
    image.putdata([(10, 20, 30, 255), (200, 210, 220, 0)])
    extractor.load_texture = lambda texture_path: (image, image.size)
    assert extractor.average_texture_color(["plant_texture"]) == (10, 20, 30)


# --- build_windows_release ------------------------------------------------

class BuildWindowsReleaseTests(unittest.TestCase):
    def test_build_environment_prepends_src_to_pythonpath(self):
        original = os.environ.get("PYTHONPATH")
        try:
            os.environ["PYTHONPATH"] = "existing-path"
            env = build_windows_release.build_environment()
        finally:
            if original is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = original

        parts = env["PYTHONPATH"].split(os.pathsep)
        self.assertEqual(parts[0], str(build_windows_release.SRC_ROOT))
        self.assertIn("existing-path", parts[1:])

    def test_default_release_main_publishes_installer_and_portable_zip(self):
        installer_path = Path("dist/release/CityGen-setup.exe")
        zip_path = Path("dist/release/CityGen-portable-windows.zip")

        with (
            mock.patch.object(build_windows_release.os, "name", "nt"),
            mock.patch.object(
                build_windows_release,
                "parse_args",
                return_value=SimpleNamespace(clean=False, include_standalone=False),
            ),
            mock.patch.object(build_windows_release, "ensure_pyinstaller"),
            mock.patch.object(build_windows_release, "load_version", return_value="1.0.0"),
            mock.patch.object(build_windows_release, "build_icon", return_value=Path("icon.ico")),
            mock.patch.object(build_windows_release, "build_portable", return_value=Path("portable/CityGen")) as build_portable,
            mock.patch.object(build_windows_release, "build_installer", return_value=installer_path),
            mock.patch.object(build_windows_release, "build_zip", return_value=zip_path) as build_zip,
            mock.patch.object(build_windows_release, "build_onefile") as build_onefile,
            mock.patch.object(build_windows_release, "prune_release_artifacts") as prune_release_artifacts,
        ):
            with redirect_stdout(io.StringIO()):
                result = build_windows_release.main()

        self.assertEqual(result, 0)
        build_zip.assert_called_once_with(build_portable.return_value)
        build_onefile.assert_not_called()
        prune_release_artifacts.assert_called_once_with(
            keep_installer=True,
            keep_zip=True,
            keep_exe=False,
        )


if __name__ == "__main__":
    unittest.main()
