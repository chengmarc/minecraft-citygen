import importlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

roads_extract = importlib.import_module("pipeline.01_roads_extract")


class RoadsExtractTests(unittest.TestCase):
    def test_run_removes_stale_schems_before_extracting(self):
        with tempfile.TemporaryDirectory() as tempdir:
            out_dir = Path(tempdir)
            stale = out_dir / "stale.schem"
            stale.write_text("old", encoding="utf-8")

            fake_file = mock.Mock()

            with mock.patch.object(roads_extract, "OUT", str(out_dir)), \
                 mock.patch.object(roads_extract, "read_signs", return_value=[(1, 1, "fresh")]), \
                 mock.patch.object(roads_extract, "components", return_value=[[0, 2, 0, 2]]), \
                 mock.patch.object(roads_extract, "strip_markers", return_value=[0, 2, 0, 2]), \
                 mock.patch.object(roads_extract, "y_extent", return_value=(65, 70)), \
                 mock.patch.object(roads_extract, "build_schem", return_value=(fake_file, (3, 6, 3), 4)):
                result = roads_extract.run()

            self.assertFalse(stale.exists())
            self.assertEqual(result["count"], 1)
            fake_file.save.assert_called_once_with(str(out_dir / "fresh.schem"))

    def test_run_raises_when_no_assets_were_extracted(self):
        with tempfile.TemporaryDirectory() as tempdir:
            out_dir = Path(tempdir)
            stale = out_dir / "stale.schem"
            stale.write_text("old", encoding="utf-8")

            with mock.patch.object(roads_extract, "OUT", str(out_dir)), \
                 mock.patch.object(roads_extract, "read_signs", return_value=[]), \
                 mock.patch.object(roads_extract, "components", return_value=[]):
                with self.assertRaisesRegex(RuntimeError, "found no assets"):
                    roads_extract.run()

            self.assertFalse(stale.exists())


if __name__ == "__main__":
    unittest.main()
