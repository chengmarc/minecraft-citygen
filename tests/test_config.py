"""Configuration layer: region models, env parsing, path discovery, versions."""
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from config import path as config_path
from config import versions as vc
from config.models import BlockRegion, BuildRegion


# --- region models & config.world env parsing -----------------------------

class RegionAndWorldConfigTests(unittest.TestCase):
    def test_block_and_build_regions_round_trip_through_xyz_and_env(self):
        block = BlockRegion.from_xyz_pair((1, 2, 3), (4, 5, 6))
        self.assertEqual(block.as_tuple(), ((1, 2, 3), (4, 5, 6)))
        self.assertEqual(block.to_env_value(), "((1, 2, 3), (4, 5, 6))")
        # Legacy flat 6-tuple shape decodes to the same region.
        self.assertEqual(BlockRegion.from_values((1, 4, 3, 6, 2, 5)).as_tuple(), ((1, 2, 3), (4, 5, 6)))

        build = BuildRegion.from_values((2, (1, 2, 3), (4, 5, 6)))
        self.assertEqual(build.as_tuple(), (2, (1, 2, 3), (4, 5, 6)))
        self.assertEqual(build.to_env_value(), "2, ((1, 2, 3), (4, 5, 6))")

    def test_config_world_accepts_new_and_legacy_env_formats(self):
        original = importlib.import_module("config.world")
        try:
            with mock.patch.dict(
                os.environ,
                {
                    "MC_CITY_ROAD_BOX": "((1, 2, 3), (4, 5, 6))",
                    "MC_CITY_BUILD_TYPES": "1, ((7, 8, 9), (10, 11, 12)); 2, 13, 16, 15, 18, 14, 17",
                },
                clear=False,
            ):
                config_world = importlib.reload(original)

            self.assertEqual(config_world.ROAD_BOX.as_tuple(), ((1, 2, 3), (4, 5, 6)))
            self.assertEqual(config_world.BUILD_TYPES[0].as_tuple(), (1, (7, 8, 9), (10, 11, 12)))
            self.assertEqual(config_world.BUILD_TYPES[1].as_tuple(), (2, (13, 14, 15), (16, 17, 18)))
        finally:
            importlib.reload(original)

    def test_save_path_falls_back_to_default_when_env_override_is_empty(self):
        original = importlib.import_module("config.world")
        try:
            with mock.patch.dict(os.environ, {"MC_CITY_SAVE": ""}, clear=False):
                config_world = importlib.reload(original)
            self.assertEqual(config_world.SAVE, config_world.DEFAULT_WORLD)
        finally:
            importlib.reload(original)


# --- path discovery -------------------------------------------------------

class PathDiscoveryTests(unittest.TestCase):
    def test_region_dir_candidates_support_save_root_and_region_dir(self):
        save_root = Path("C:/Users/Test/.minecraft/saves/MyWorld")
        self.assertEqual(
            config_path.region_dir_candidates(save_root),
            [
                os.path.normpath("C:/Users/Test/.minecraft/saves/MyWorld/region"),
                os.path.normpath("C:/Users/Test/.minecraft/saves/MyWorld/dimensions/minecraft/overworld/region"),
            ],
        )

        region_dir = Path("C:/Users/Test/.minecraft/saves/MyWorld/region")
        self.assertEqual(
            config_path.region_dir_candidates(region_dir),
            [os.path.normpath("C:/Users/Test/.minecraft/saves/MyWorld/region")],
        )

    def test_resolve_region_dir_prefers_existing_candidate(self):
        with tempfile.TemporaryDirectory() as tempdir:
            save_root = Path(tempdir) / "world"
            expected = save_root / "dimensions" / "minecraft" / "overworld" / "region"
            expected.mkdir(parents=True)
            self.assertEqual(config_path.resolve_region_dir(save_root), os.path.normpath(str(expected)))

    def test_resolve_region_dir_prefers_candidate_with_region_files(self):
        with tempfile.TemporaryDirectory() as tempdir:
            save_root = Path(tempdir) / "world"
            root_region = save_root / "region"
            nested_region = save_root / "dimensions" / "minecraft" / "overworld" / "region"
            root_region.mkdir(parents=True)
            nested_region.mkdir(parents=True)
            (nested_region / "r.0.0.mca").write_bytes(b"region")

            self.assertEqual(config_path.resolve_region_dir(save_root), os.path.normpath(str(nested_region)))
            self.assertTrue(config_path.has_region_files(save_root))


# --- app-root selection ---------------------------------------------------

class AppRootTests(unittest.TestCase):
    def test_repo_checkout_root_detects_src_dev_tree(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            src_root = root / "src"
            for name in ("config", "engine", "gui", "pipeline"):
                (src_root / name).mkdir(parents=True, exist_ok=True)
            (root / "application.pyw").write_text("", encoding="utf-8")
            self.assertEqual(config_path._repo_checkout_root(str(src_root)), os.path.normpath(str(root)))

    def test_app_root_uses_user_data_outside_repo_checkout(self):
        with tempfile.TemporaryDirectory() as tempdir:
            source_root = Path(tempdir) / "site-packages" / "src"
            source_root.mkdir(parents=True)
            local_appdata = Path(tempdir) / "LocalAppData"
            with mock.patch.object(config_path, "SOURCE_ROOT", str(source_root)):
                with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(local_appdata)}, clear=False):
                    self.assertEqual(
                        config_path._app_root(),
                        os.path.normpath(str(local_appdata / config_path.APP_NAME)),
                    )


# --- version detection ----------------------------------------------------

class VersionTests(unittest.TestCase):
    def test_release_name_for_known_unknown_and_hard_floor(self):
        self.assertEqual(vc.HARD_FLOOR_DATA_VERSION, 3463)  # Minecraft 1.20
        self.assertEqual(vc.release_name_for(3463), "1.20")
        self.assertEqual(vc.release_name_for(3465), "1.20.1")
        # Unmapped versions fall back to the raw DataVersion.
        self.assertEqual(vc.release_name_for(999999), "DataVersion 999999")

    def test_detect_world_data_version_reads_bundled_world_and_handles_absent(self):
        world = Path(__file__).resolve().parents[1] / "src" / "config" / "default_world"
        self.assertEqual(vc.detect_world_data_version(str(world)), 3463)  # bundled world is 1.20

        with tempfile.TemporaryDirectory() as tempdir:
            self.assertIsNone(vc.detect_world_data_version(tempdir))  # no level.dat
            self.assertIsNone(vc.detect_world_data_version(""))
            (Path(tempdir) / "level.dat").write_bytes(b"not a real nbt file")
            self.assertIsNone(vc.detect_world_data_version(tempdir))  # corrupt


if __name__ == "__main__":
    unittest.main()
