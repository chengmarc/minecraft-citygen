import importlib
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

roads_extract = importlib.import_module("pipeline.01_roads.extract")


def _component(boundary, cuboid, *, ground_y=None):
    if ground_y is None:
        ground_y = cuboid[2]
    return types.SimpleNamespace(boundary=boundary, cuboids=[cuboid], ground_y=ground_y)


class RoadsExtractTests(unittest.TestCase):
    def test_run_removes_stale_schems_before_extracting(self):
        with tempfile.TemporaryDirectory() as tempdir:
            out_dir = Path(tempdir)
            stale = out_dir / "stale.schem"
            stale.write_text("old", encoding="utf-8")

            component = _component((0, 2, 0, 2), (0, 2, 65, 70, 0, 2), ground_y=67)
            cells = [[["minecraft:stone"]]]

            with mock.patch.object(roads_extract, "OUT", str(out_dir)), \
                 mock.patch.object(roads_extract, "get_world", return_value=mock.Mock()), \
                 mock.patch.object(roads_extract, "ground_shift", return_value=0), \
                 mock.patch.object(roads_extract, "read_names", return_value=[(1, 1, "fresh")]), \
                 mock.patch.object(roads_extract, "detect_assets", return_value=([component], [])), \
                 mock.patch.object(roads_extract, "extract_cuboid", return_value=(cells, [])), \
                 mock.patch.object(roads_extract, "write_sponge_schem_cells") as write_schem:
                result = roads_extract.run()

            self.assertFalse(stale.exists())
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["items"], ["fresh"])
            write_schem.assert_called_once()
            self.assertEqual(write_schem.call_args.args[1], str(out_dir / "fresh.schem"))
            self.assertEqual(write_schem.call_args.kwargs["offset"], (0, -2, 0))

    def test_run_skips_components_without_a_matching_sign(self):
        with tempfile.TemporaryDirectory() as tempdir:
            out_dir = Path(tempdir)
            component = _component((100, 102, 100, 102), (100, 102, 65, 70, 100, 102))

            with mock.patch.object(roads_extract, "OUT", str(out_dir)), \
                 mock.patch.object(roads_extract, "get_world", return_value=mock.Mock()), \
                 mock.patch.object(roads_extract, "ground_shift", return_value=0), \
                 mock.patch.object(roads_extract, "read_names", return_value=[(1, 1, "fresh")]), \
                 mock.patch.object(roads_extract, "detect_assets", return_value=([component], [])), \
                 mock.patch.object(roads_extract, "extract_cuboid", return_value=([[["minecraft:stone"]]], [])), \
                 mock.patch.object(roads_extract, "write_sponge_schem_cells"):
                # the only component has no sign inside its boundary -> nothing extracted
                with self.assertRaisesRegex(RuntimeError, "found no assets"):
                    roads_extract.run()

    def test_run_raises_when_no_components_were_found(self):
        with tempfile.TemporaryDirectory() as tempdir:
            out_dir = Path(tempdir)
            stale = out_dir / "stale.schem"
            stale.write_text("old", encoding="utf-8")

            with mock.patch.object(roads_extract, "OUT", str(out_dir)), \
                 mock.patch.object(roads_extract, "get_world", return_value=mock.Mock()), \
                 mock.patch.object(roads_extract, "ground_shift", return_value=0), \
                 mock.patch.object(roads_extract, "read_names", return_value=[]), \
                 mock.patch.object(roads_extract, "detect_assets", return_value=([], [])):
                with self.assertRaisesRegex(RuntimeError, "found no assets"):
                    roads_extract.run()

            self.assertFalse(stale.exists())


if __name__ == "__main__":
    unittest.main()
