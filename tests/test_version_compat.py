from pathlib import Path

from config import version_compat as vc


def test_release_table_is_ordered_and_covers_supported_range():
    versions = [ver for _, ver in vc.RELEASES]
    assert versions == sorted(versions)
    # The table is clamped to the hard floor: 1.19.4 is the oldest entry, and
    # everything below it is dropped (not a known release for resolution).
    assert vc.SUPPORTED_FLOOR == vc.HARD_FLOOR_DATA_VERSION == vc.data_version_for("1.19.4")
    assert vc.data_version_for("1.18") is None
    assert vc.data_version_for("1.19") is None
    # Bounds track the ends of the loaded table (oldest floor, newest ceiling).
    assert vc.SUPPORTED_FLOOR == vc.RELEASES[0][1]
    assert vc.FALLBACK_DATA_VERSION == vc.RELEASES[-1][1]


def test_data_version_for_unknown_release_is_none():
    assert vc.data_version_for("1.17") is None
    assert vc.data_version_for("nonsense") is None


def test_release_name_for_exact_and_approximate():
    assert vc.release_name_for(4790) == "26.1.2"
    # Between 1.20.1 (3465) and 1.20.2 (3578) -> anchored to the lower release.
    assert vc.release_name_for(3500).startswith("1.20.1+")
    assert "pre-1.19.4" in vc.release_name_for(1000)


def test_detect_world_data_version_reads_bundled_world():
    root = Path(__file__).resolve().parents[1]
    world = root / "src" / "config" / "default_world"
    assert vc.detect_world_data_version(str(world)) == 3337  # bundled world is 1.19.4


def test_detect_world_data_version_missing_returns_none(tmp_path):
    assert vc.detect_world_data_version(str(tmp_path)) is None
    assert vc.detect_world_data_version("") is None


def test_detect_world_data_version_corrupt_returns_none(tmp_path):
    (tmp_path / "level.dat").write_bytes(b"not a real nbt file")
    assert vc.detect_world_data_version(str(tmp_path)) is None


def test_load_releases_json_roundtrip(tmp_path):
    path = tmp_path / "mc_versions.json"
    path.write_text('{"1.19": 3105, "1.18": 2860}', encoding="utf-8")
    # Loader sorts ascending by data_version regardless of file order.
    assert vc.load_releases_json(str(path)) == (("1.18", 2860), ("1.19", 3105))


def test_load_releases_json_returns_none_when_absent_or_corrupt(tmp_path):
    assert vc.load_releases_json(str(tmp_path / "missing.json")) is None
    corrupt = tmp_path / "bad.json"
    corrupt.write_text("not valid json", encoding="utf-8")
    assert vc.load_releases_json(str(corrupt)) is None
