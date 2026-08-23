from pathlib import Path

from config import version_compat as vc


def test_hard_floor_is_1_19_4():
    assert vc.HARD_FLOOR_DATA_VERSION == 3337


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
