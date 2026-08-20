import importlib.util
import sys
from pathlib import Path

from PIL import Image


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "tools" / "update_render_colors.py"
SPEC = importlib.util.spec_from_file_location("update_render_colors", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

DEFAULT_OUTPUT = MODULE.DEFAULT_OUTPUT
ROOT = MODULE.ROOT
TOOLS_DIR = MODULE.TOOLS_DIR
MinecraftTopColorExtractor = MODULE.MinecraftTopColorExtractor
download_client_jar = MODULE.download_client_jar
resolve_version_metadata = MODULE.resolve_version_metadata
write_csv = MODULE.write_csv


def test_default_output_points_to_packaged_csv():
    assert ROOT == Path(__file__).resolve().parents[1]
    assert DEFAULT_OUTPUT == ROOT / "src" / "engine" / "color_render.csv"
    assert TOOLS_DIR == ROOT / "tools"


def test_write_csv_includes_expected_header(tmp_path):
    output = tmp_path / "color_render.csv"
    write_csv([("minecraft:stone", 1, 2, 3)], output)

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

    version_id, metadata = resolve_version_metadata(None)

    assert version_id == "1.2.3"
    assert metadata["url"] == "https://example.invalid/1.2.3.json"


def test_resolve_version_metadata_uses_requested_version(monkeypatch):
    manifest = {
        "latest": {"release": "1.2.3"},
        "versions": [
            {"id": "1.2.3", "url": "https://example.invalid/1.2.3.json"},
            {"id": "1.2.2", "url": "https://example.invalid/1.2.2.json"},
        ],
    }

    monkeypatch.setattr(MODULE, "load_json_url", lambda url: manifest)

    version_id, metadata = resolve_version_metadata("1.2.2")

    assert version_id == "1.2.2"
    assert metadata["url"] == "https://example.invalid/1.2.2.json"


def test_download_client_jar_reuses_matching_cached_file(monkeypatch, tmp_path):
    version_id = "1.2.3"
    jar_path = tmp_path / f"minecraft-client-{version_id}.jar"
    jar_bytes = b"cached-jar"
    jar_path.write_bytes(jar_bytes)

    expected_sha1 = MODULE.hashlib.sha1(jar_bytes).hexdigest()

    monkeypatch.setattr(MODULE, "TOOLS_DIR", tmp_path)
    monkeypatch.setattr(
        MODULE,
        "resolve_version_metadata",
        lambda version: (version_id, {"url": "https://example.invalid/version.json"}),
    )
    monkeypatch.setattr(
        MODULE,
        "load_json_url",
        lambda url: {
            "downloads": {
                "client": {
                    "url": "https://example.invalid/client.jar",
                    "sha1": expected_sha1,
                }
            }
        },
    )

    def unexpected_urlopen(*args, **kwargs):
        raise AssertionError("cache hit should not download")

    monkeypatch.setattr(MODULE.urllib.request, "urlopen", unexpected_urlopen)

    actual_version, actual_path = download_client_jar(version_id)

    assert actual_version == version_id
    assert actual_path == jar_path


def test_average_block_color_falls_back_to_texture_average(monkeypatch):
    extractor = object.__new__(MinecraftTopColorExtractor)

    monkeypatch.setattr(extractor, "collect_faces", lambda block_name: [])
    monkeypatch.setattr(extractor, "collect_texture_paths", lambda block_name: ["plant_texture"])
    monkeypatch.setattr(extractor, "average_texture_color", lambda texture_paths: (12, 34, 56))

    assert extractor.average_block_color("short_grass") == (12, 34, 56)


def test_average_texture_color_ignores_transparent_pixels():
    extractor = object.__new__(MinecraftTopColorExtractor)
    image = Image.new("RGBA", (2, 1))
    image.putdata([(10, 20, 30, 255), (200, 210, 220, 0)])
    extractor.load_texture = lambda texture_path: (image, image.size)

    assert extractor.average_texture_color(["plant_texture"]) == (10, 20, 30)
