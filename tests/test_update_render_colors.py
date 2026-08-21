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
    assert DEFAULT_OUTPUT == ROOT / "src" / "config" / "color_render.csv"
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

    # "stone" is not biome-tinted, so the fallback average is returned unchanged.
    assert extractor.average_block_color("stone") == (12, 34, 56)


def test_average_block_color_tints_biome_block_in_fallback(monkeypatch):
    extractor = object.__new__(MinecraftTopColorExtractor)

    monkeypatch.setattr(extractor, "collect_faces", lambda block_name: [])
    monkeypatch.setattr(extractor, "collect_texture_paths", lambda block_name: ["leaf_texture"])
    monkeypatch.setattr(extractor, "average_texture_color", lambda texture_paths: (200, 200, 200))

    expected = MODULE._apply_tint((200, 200, 200), MODULE.FOLIAGE_TINT)
    assert extractor.average_block_color("oak_leaves") == expected


def test_average_block_color_tints_only_faces_with_tintindex(monkeypatch):
    extractor = object.__new__(MinecraftTopColorExtractor)
    full_cube_top = MODULE.Face(
        texture_path="leaf_texture",
        x1=0, x2=16, z1=0, z2=16, y=16,
        uv=(0, 0, 16, 16), rotation=0, order=0, tinted=True,
    )
    monkeypatch.setattr(extractor, "collect_faces", lambda block_name: [full_cube_top])
    solid = Image.new("RGBA", (16, 16), (150, 150, 150, 255))
    monkeypatch.setattr(extractor, "load_texture", lambda texture_path: (solid, solid.size))

    expected = MODULE._apply_tint((150, 150, 150), MODULE.FOLIAGE_TINT)
    assert extractor.average_block_color("oak_leaves") == expected

    # An identical block whose face carries no tintindex is left untinted.
    plain_top = MODULE.Face(
        texture_path="leaf_texture",
        x1=0, x2=16, z1=0, z2=16, y=16,
        uv=(0, 0, 16, 16), rotation=0, order=0, tinted=False,
    )
    monkeypatch.setattr(extractor, "collect_faces", lambda block_name: [plain_top])
    assert extractor.average_block_color("oak_leaves") == (150, 150, 150)


def test_average_block_color_skips_tint_for_coloured_texture(monkeypatch):
    # A tintindex face whose texture is already saturated (not a grayscale mask)
    # must be left alone, even for a block in a tinted category.
    extractor = object.__new__(MinecraftTopColorExtractor)
    tinted_top = MODULE.Face(
        texture_path="leaf_texture",
        x1=0, x2=16, z1=0, z2=16, y=16,
        uv=(0, 0, 16, 16), rotation=0, order=0, tinted=True,
    )
    monkeypatch.setattr(extractor, "collect_faces", lambda block_name: [tinted_top])
    coloured = Image.new("RGBA", (16, 16), (210, 120, 150, 255))
    monkeypatch.setattr(extractor, "load_texture", lambda texture_path: (coloured, coloured.size))

    assert extractor.average_block_color("oak_leaves") == (210, 120, 150)


def test_average_texture_color_ignores_transparent_pixels():
    extractor = object.__new__(MinecraftTopColorExtractor)
    image = Image.new("RGBA", (2, 1))
    image.putdata([(10, 20, 30, 255), (200, 210, 220, 0)])
    extractor.load_texture = lambda texture_path: (image, image.size)

    assert extractor.average_texture_color(["plant_texture"]) == (10, 20, 30)
