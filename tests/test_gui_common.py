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


if __name__ == "__main__":
    unittest.main()
