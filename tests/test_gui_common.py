"""GUI helpers that don't need Qt: the shared artifact clearing.

``clear_pipeline_artifacts`` is used both on launch and when switching worlds, so
both paths get the same clean slate.
"""
import os
import tempfile
import unittest
from unittest import mock

from gui.core import common


class ClearPipelineArtifactsTests(unittest.TestCase):
    def test_wipes_pipeline_artifacts_but_keeps_saves(self):
        with tempfile.TemporaryDirectory() as root:
            saves = os.path.join(root, "saves")
            world = os.path.join(saves, "seed_5_world")
            os.makedirs(world)
            open(os.path.join(world, "level.dat"), "wb").close()

            os.makedirs(os.path.join(root, "roads", "production"))
            open(os.path.join(root, "roads", "production", "a.schem"), "wb").close()
            open(os.path.join(root, "loose.png"), "wb").close()

            with mock.patch.object(common, "ARTIFACTS", root), mock.patch.object(common, "SAVES", saves):
                common.clear_pipeline_artifacts()

            self.assertTrue(os.path.exists(os.path.join(world, "level.dat")))  # saves kept
            self.assertFalse(os.path.exists(os.path.join(root, "roads")))      # pipeline wiped
            self.assertFalse(os.path.exists(os.path.join(root, "loose.png")))  # loose files wiped


class ExtractedAssetsReadyTests(unittest.TestCase):
    def test_requires_only_road_and_build_contact_sheets(self):
        with tempfile.TemporaryDirectory() as root:
            road_sheet = os.path.join(root, "roads", "production", "_contact_sheet.png")
            build_sheet = os.path.join(root, "builds", "production", "_contact_sheet.png")
            os.makedirs(os.path.dirname(road_sheet))
            os.makedirs(os.path.dirname(build_sheet))

            with (
                mock.patch.object(common, "ROAD_CONTACT_SHEET", road_sheet),
                mock.patch.object(common, "BUILD_CONTACT_SHEET", build_sheet),
            ):
                self.assertFalse(common.extracted_assets_ready())

                open(road_sheet, "wb").close()
                self.assertFalse(common.extracted_assets_ready())

                open(build_sheet, "wb").close()
                self.assertTrue(common.extracted_assets_ready())


if __name__ == "__main__":
    unittest.main()
