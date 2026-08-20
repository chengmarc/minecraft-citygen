import importlib.util
import os
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "packaging" / "build_windows_release.py"
SPEC = importlib.util.spec_from_file_location("build_windows_release", MODULE_PATH)
build_windows_release = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_windows_release)


class BuildWindowsReleaseTests(unittest.TestCase):
    def test_build_environment_prepends_src_to_pythonpath(self):
        original = os.environ.get("PYTHONPATH")
        try:
            os.environ["PYTHONPATH"] = "existing-path"
            env = build_windows_release.build_environment()
        finally:
            if original is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = original

        parts = env["PYTHONPATH"].split(os.pathsep)
        self.assertEqual(parts[0], str(build_windows_release.SRC_ROOT))
        self.assertIn("existing-path", parts[1:])

    def test_build_environment_sets_pythonpath_when_missing(self):
        original = os.environ.pop("PYTHONPATH", None)
        try:
            env = build_windows_release.build_environment()
        finally:
            if original is not None:
                os.environ["PYTHONPATH"] = original

        self.assertEqual(env["PYTHONPATH"], str(build_windows_release.SRC_ROOT))


if __name__ == "__main__":
    unittest.main()
