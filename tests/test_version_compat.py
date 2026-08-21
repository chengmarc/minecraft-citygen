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


def test_block_min_data_version_defaults_to_floor_for_stable_blocks():
    assert vc.block_min_data_version("minecraft:stone") == vc.SUPPORTED_FLOOR
    assert vc.block_min_data_version("minecraft:oak_planks[axis=y]") == vc.SUPPORTED_FLOOR


def test_block_min_data_version_flags_modern_blocks():
    # Clean-cutover blocks map to an exact release (renames / late additions).
    assert vc.block_min_data_version("minecraft:short_grass") == vc.data_version_for("1.20.3")
    assert vc.block_min_data_version("minecraft:pale_oak_shelf") == vc.data_version_for("1.21.9")
    # Cherry wood registered right at the 1.19.4 hard floor, so it sits exactly
    # on it rather than above.
    assert vc.block_min_data_version("minecraft:cherry_planks") == vc.SUPPORTED_FLOOR


def test_bundled_assets_report_expected_floor():
    # The bundled city's floor is driven by its newest block (pale_oak_shelf, 1.21.9).
    bundled_modern = [
        "minecraft:mangrove_stairs", "minecraft:mud_bricks", "minecraft:cherry_planks",
        "minecraft:short_grass", "minecraft:pale_oak_fence", "minecraft:wildflowers",
        "minecraft:pale_oak_shelf",
    ]
    assert vc.min_compatible_data_version(bundled_modern) == vc.data_version_for("1.21.9")


def test_ancient_blocks_are_not_flagged():
    # Blocks that exist at or before the floor are assumed safe.
    assert vc.block_min_data_version("minecraft:bamboo") == vc.SUPPORTED_FLOOR
    assert vc.block_min_data_version("minecraft:stone") == vc.SUPPORTED_FLOOR


def test_downgrade_block_applies_renames_below_threshold():
    v194 = vc.data_version_for("1.19.4")
    assert vc.downgrade_block("minecraft:short_grass", v194) == "minecraft:grass"
    assert vc.downgrade_block("minecraft:iron_chain[axis=y]", v194) == "minecraft:chain[axis=y]"
    # Bare (un-namespaced) input is accepted too.
    assert vc.downgrade_block("short_grass", v194) == "minecraft:grass"


def test_downgrade_block_is_noop_at_or_above_threshold():
    # short_grass was introduced at 1.20.3; targeting that or newer keeps it.
    assert vc.downgrade_block("minecraft:short_grass", vc.data_version_for("1.20.3")) == "minecraft:short_grass"
    assert vc.downgrade_block("minecraft:iron_chain", vc.FALLBACK_DATA_VERSION) == "minecraft:iron_chain"
    # Non-renameable blocks pass through untouched.
    assert vc.downgrade_block("minecraft:stone", vc.SUPPORTED_FLOOR) == "minecraft:stone"


def test_effective_min_reflects_rename_chain():
    # short_grass/iron_chain can be written as ancient ids, so their floor is the base.
    assert vc.effective_min_data_version("minecraft:short_grass") == vc.SUPPORTED_FLOOR
    assert vc.effective_min_data_version("minecraft:iron_chain") == vc.SUPPORTED_FLOOR


def test_compatibility_report_separates_renames_from_holes():
    report = vc.compatibility_report(
        ["minecraft:stone", "minecraft:short_grass", "minecraft:iron_chain", "minecraft:pale_oak_fence"],
        vc.data_version_for("1.19.4"),
    )
    renamed = {item["block"]: item["as"] for item in report["renamed"]}
    assert renamed == {"minecraft:short_grass": "minecraft:grass", "minecraft:iron_chain": "minecraft:chain"}
    # pale_oak_fence has no rename, so it is a genuine hole.
    assert [item["block"] for item in report["offending"]] == ["minecraft:pale_oak_fence"]
    assert report["ok"] is False


def test_compatibility_report_ok_when_only_renames_needed():
    report = vc.compatibility_report(
        ["minecraft:stone", "minecraft:short_grass", "minecraft:iron_chain"],
        vc.data_version_for("1.19.4"),
    )
    assert report["ok"] is True
    assert report["offending"] == []
    assert len(report["renamed"]) == 2


def test_min_compatible_version_is_driven_by_newest_block():
    blocks = ["minecraft:stone", "minecraft:cherry_planks", "minecraft:wildflowers"]
    assert vc.min_compatible_data_version(blocks) == vc.data_version_for("1.21.5")


def test_compatibility_report_ok_when_target_meets_floor():
    # mud_bricks (1.19) sits below the hard floor, so it can never offend and the
    # reported floor collapses to 1.19.4.
    report = vc.compatibility_report(
        ["minecraft:stone", "minecraft:mud_bricks"], vc.SUPPORTED_FLOOR
    )
    assert report["ok"] is True
    assert report["offending"] == []
    assert report["floor_release"] == "1.19.4"


def test_compatibility_report_lists_offending_blocks_sorted_newest_first():
    # Both blocks post-date the hard floor, so targeting 1.19.4 leaves both as
    # holes, sorted newest-first.
    blocks = ["minecraft:stone", "minecraft:pale_oak_fence", "minecraft:pale_oak_shelf"]
    report = vc.compatibility_report(blocks, vc.SUPPORTED_FLOOR)
    assert report["ok"] is False
    offenders = [item["block"] for item in report["offending"]]
    assert offenders == ["minecraft:pale_oak_shelf", "minecraft:pale_oak_fence"]
    # Floor is the newest offender's introduction; tracks the loaded data.
    assert report["floor_release"] == vc.release_name_for(
        vc.block_min_data_version("minecraft:pale_oak_shelf")
    )


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


def test_load_block_versions_json_roundtrip(tmp_path):
    path = tmp_path / "block_versions.json"
    path.write_text(
        '{"minecraft:pale_oak_planks": 4189, "minecraft:mud": 3105}',
        encoding="utf-8",
    )
    assert vc.load_block_versions_json(str(path)) == {
        "minecraft:pale_oak_planks": 4189,
        "minecraft:mud": 3105,
    }


def test_json_loaders_return_none_when_absent_or_corrupt(tmp_path):
    assert vc.load_releases_json(str(tmp_path / "missing.json")) is None
    assert vc.load_block_versions_json(str(tmp_path / "missing.json")) is None
    corrupt = tmp_path / "bad.json"
    corrupt.write_text("not valid json", encoding="utf-8")
    assert vc.load_releases_json(str(corrupt)) is None
    assert vc.load_block_versions_json(str(corrupt)) is None
