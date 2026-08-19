import os
import tempfile
import unittest
from pathlib import Path

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

    def test_is_world_save_checks_region_candidates(self):
        with tempfile.TemporaryDirectory() as tempdir:
            save_root = Path(tempdir) / "world"
            self.assertFalse(paths.is_world_save(save_root))
            (save_root / "dimensions" / "minecraft" / "overworld" / "region").mkdir(parents=True)
            self.assertTrue(paths.is_world_save(save_root))


if __name__ == "__main__":
    unittest.main()
