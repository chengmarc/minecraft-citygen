import importlib.util
import sys
from pathlib import Path

from config import version_compat as vc

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "tools" / "update_mc_versions.py"
SPEC = importlib.util.spec_from_file_location("update_mc_versions", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_write_releases_json_is_loadable_by_version_compat(tmp_path):
    releases = {3105: "1.19", 2860: "1.18"}
    out = tmp_path / "versions.json"
    MODULE.write_releases_json(releases, out)
    assert vc.load_releases_json(str(out)) == (("1.18", 2860), ("1.19", 3105))
