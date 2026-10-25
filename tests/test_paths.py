"""Paths: where the app keeps its data."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from citygen import paths


# --- frozen app data root -------------------------------------------------

class CheckoutRootTests(unittest.TestCase):
    def test_a_checkout_keeps_its_data_at_the_repo_root_not_beside_the_entry_script(self):
        with tempfile.TemporaryDirectory() as repo:
            src = Path(repo) / "src"
            (src / "citygen").mkdir(parents=True)
            (src / "application.pyw").touch()
            (Path(repo) / "pyproject.toml").touch()

            root = paths._repo_checkout_root(str(src))

        self.assertEqual(Path(root), Path(repo).resolve())


class FrozenAppRootTests(unittest.TestCase):
    def test_packaged_app_writes_to_the_real_package_folder(self):
        local = str(Path.home() / "AppData" / "Local")
        with mock.patch.object(paths, "_package_family_name", return_value="CityGen_abc123"), \
                mock.patch.dict(os.environ, {"LOCALAPPDATA": local}):
            root = paths._frozen_app_root()
        expected = Path(local) / "Packages" / "CityGen_abc123" / "LocalCache" / "Local" / "MC CityGen"
        self.assertEqual(root, os.path.normpath(expected))

    def test_unwritable_exe_dir_falls_back_to_user_data_root(self):
        with mock.patch.object(paths, "_package_family_name", return_value=""), \
                mock.patch.object(paths, "_is_writable_dir", return_value=False):
            self.assertEqual(paths._frozen_app_root(), paths._user_data_root())

    def test_is_writable_dir_probes_with_a_real_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            self.assertTrue(paths._is_writable_dir(Path(tempdir)))
            self.assertEqual(os.listdir(tempdir), [])  # the probe cleans up after itself
            self.assertFalse(paths._is_writable_dir(Path(tempdir) / "missing"))


# --- legacy data migration ---------------------------------------------------

class LegacyDataMigrationTests(unittest.TestCase):
    def _legacy_root(self, root: Path) -> None:
        (root / "artifacts" / "05_world" / "saves" / "World 5").mkdir(parents=True)
        (root / "src" / "config").mkdir(parents=True)
        (root / "src" / "config" / "citygen.json").write_text("{}", encoding="utf-8")

    def test_moves_artifacts_and_settings_into_appdata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._legacy_root(root)

            paths._migrate_legacy_data(root, installed=True)

            self.assertTrue((root / "appdata" / "05_world" / "saves" / "World 5").is_dir())
            self.assertTrue((root / "appdata" / "citygen.json").is_file())
            self.assertFalse((root / "artifacts").exists())
            self.assertFalse((root / "src").exists())  # an installed copy's src/ held only the settings

    def test_keeps_src_in_a_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._legacy_root(root)

            paths._migrate_legacy_data(root, installed=False)

            self.assertTrue((root / "appdata" / "citygen.json").is_file())
            self.assertTrue((root / "src" / "config").is_dir())

    def test_leaves_existing_appdata_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._legacy_root(root)
            (root / "appdata").mkdir()
            (root / "appdata" / "citygen.json").write_text('{"new": true}', encoding="utf-8")

            paths._migrate_legacy_data(root, installed=True)

            self.assertTrue((root / "artifacts").is_dir())  # not merged into an existing appdata/
            self.assertEqual((root / "appdata" / "citygen.json").read_text(encoding="utf-8"), '{"new": true}')
