import tempfile
import unittest
from pathlib import Path

from engine.render_topdown import region_world_bounds


class WorldPreviewTests(unittest.TestCase):
    def test_region_world_bounds_uses_region_file_coordinates(self):
        with tempfile.TemporaryDirectory() as tempdir:
            region_dir = Path(tempdir)
            for name in ("r.-1.-1.mca", "r.-1.0.mca", "r.0.-1.mca"):
                (region_dir / name).write_bytes(b"")

            self.assertEqual(region_world_bounds(region_dir), (-512, 511, -512, 511))

    def test_region_world_bounds_requires_region_files(self):
        with tempfile.TemporaryDirectory() as tempdir:
            with self.assertRaises(FileNotFoundError):
                region_world_bounds(tempdir)


if __name__ == "__main__":
    unittest.main()
