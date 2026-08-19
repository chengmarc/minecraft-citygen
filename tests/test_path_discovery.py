import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from config import path_discovery as paths


class PathDiscoveryTests(unittest.TestCase):
    def test_region_dir_candidates_support_save_root_and_region_dir(self):
        save_root = Path("C:/Users/Test/.minecraft/saves/MyWorld")
        self.assertEqual(
            paths.region_dir_candidates(save_root),
            [
                os.path.normpath("C:/Users/Test/.minecraft/saves/MyWorld/region"),
                os.path.normpath("C:/Users/Test/.minecraft/saves/MyWorld/dimensions/minecraft/overworld/region"),
            ],
        )

        region_dir = Path("C:/Users/Test/.minecraft/saves/MyWorld/region")
        self.assertEqual(
            paths.region_dir_candidates(region_dir),
            [os.path.normpath("C:/Users/Test/.minecraft/saves/MyWorld/region")],
        )

    def test_resolve_region_dir_prefers_existing_candidate(self):
        with tempfile.TemporaryDirectory() as tempdir:
            save_root = Path(tempdir) / "world"
            expected = save_root / "dimensions" / "minecraft" / "overworld" / "region"
            expected.mkdir(parents=True)
            self.assertEqual(paths.resolve_region_dir(save_root), os.path.normpath(str(expected)))

    def test_discover_worldedit_schematics_falls_back_to_repo_local_dir(self):
        with tempfile.TemporaryDirectory() as tempdir:
            fallback = Path(tempdir) / "artifacts" / "worldedit"
            with mock.patch.dict(os.environ, {"APPDATA": tempdir}, clear=False):
                detected = paths.discover_worldedit_schematics("", fallback)
            self.assertEqual(detected, os.path.normpath(str(fallback)))

    def test_discover_worldedit_schematics_uses_matching_instance_dir(self):
        with tempfile.TemporaryDirectory() as tempdir:
            appdata = Path(tempdir)
            save_root = appdata / "PrismLauncher" / "instances" / "CityPack" / "minecraft" / "saves" / "MyWorld"
            worldedit_dir = appdata / "PrismLauncher" / "instances" / "CityPack" / "minecraft" / "config" / "worldedit" / "schematics"
            save_root.mkdir(parents=True)
            worldedit_dir.mkdir(parents=True)
            with mock.patch.dict(os.environ, {"APPDATA": tempdir}, clear=False):
                detected = paths.discover_worldedit_schematics(save_root)
            self.assertEqual(detected, os.path.normpath(str(worldedit_dir)))


if __name__ == "__main__":
    unittest.main()
