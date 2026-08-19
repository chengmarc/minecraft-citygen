import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from config import config_path


class ConfigPathTests(unittest.TestCase):
    def test_is_repo_checkout_detects_src_dev_tree(self):
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

    def test_user_data_root_honors_explicit_override(self):
        with tempfile.TemporaryDirectory() as tempdir:
            override = Path(tempdir) / "CityGenData"
            with mock.patch.dict(os.environ, {"MC_CITY_APP_ROOT": str(override)}, clear=False):
                self.assertEqual(config_path._user_data_root(), os.path.normpath(str(override)))

    def test_frozen_app_root_prefers_writable_executable_dir(self):
        with tempfile.TemporaryDirectory() as tempdir:
            executable = Path(tempdir) / "CityGen.exe"
            executable.write_text("", encoding="utf-8")
            root = config_path._frozen_app_root(str(executable))
            self.assertEqual(root, os.path.normpath(tempdir))


if __name__ == "__main__":
    unittest.main()
