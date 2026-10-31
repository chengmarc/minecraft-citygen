"""Windows release packaging command construction."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest


def load_build_script():
    script = Path(__file__).resolve().parents[1] / "packaging" / "build_windows_release.py"
    spec = importlib.util.spec_from_file_location("build_windows_release", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_pyinstaller_command_bundles_the_page_and_the_data():
    build = load_build_script()

    command = build.base_pyinstaller_command(onefile=False, icon_path=None)

    data = {value for flag, value in zip(command, command[1:]) if flag == "--add-data"}
    assert build.data_arg(build.SRC_ROOT / "citygen" / "gui" / "static", "citygen/gui/static") in data
    assert build.data_arg(build.DATA_DIR, "citygen/data") in data


def test_msix_version_appends_the_zero_revision_the_store_requires():
    build = load_build_script()

    assert build.msix_version("1.2.0") == "1.2.0.0"


def test_msix_manifest_renders_to_valid_xml_with_the_store_identity(monkeypatch):
    import xml.etree.ElementTree as ET

    build = load_build_script()
    monkeypatch.setattr(build, "MSIX_IDENTITY_NAME", "12345Publisher.MCCityGen")
    monkeypatch.setattr(build, "MSIX_PUBLISHER", "CN=00000000-0000-0000-0000-000000000000")
    monkeypatch.setattr(build, "MSIX_PUBLISHER_DISPLAY_NAME", "Publisher")

    root = ET.fromstring(build.render_msix_manifest("1.2.0"))

    ns = {"m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10"}
    identity = root.find("m:Identity", ns)
    assert identity.get("Name") == "12345Publisher.MCCityGen"
    assert identity.get("Version") == "1.2.0.0"
    assert root.find("m:Applications/m:Application", ns).get("Executable") == f"{build.APP_NAME}.exe"
    manifest = ET.tostring(root, encoding="unicode")
    assert [logo for logo in build.MSIX_LOGOS if f"Assets\\{logo}" not in manifest] == []


LISTING = Path(__file__).resolve().parents[1] / "store-listing"
LOCALIZATION = LISTING / "localization"


def load_render_script():
    spec = importlib.util.spec_from_file_location("render", LISTING / "generator" / "render.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def app_languages():
    from citygen.gui import server

    return sorted(path.stem for path in (server.STATIC / "i18n").glob("*.json"))


def captions():
    text = (LISTING / "generator" / "captions.js").read_text(encoding="utf-8")
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def field(listing, heading):
    return re.search(rf"^### {heading}\n+```\n(.*?)\n```", listing, re.S | re.M).group(1)


def test_every_app_language_has_its_listing_and_screenshots():
    render = load_render_script()

    assert sorted(render.LANGUAGES) == app_languages()
    assert sorted(path.stem for path in LOCALIZATION.glob("*.md")) == app_languages()
    assert sorted(captions()) == app_languages()
    for code in app_languages():
        images = [name for name, *_rest in render.IMAGES if name.startswith(f"{code}/")]
        assert len(images) == 5 + 3, code


def test_every_language_captions_every_shot():
    english = captions()["en"]
    for code, words in captions().items():
        assert words["tagline"], code
        assert words["shots"].keys() == english["shots"].keys(), code
        assert len(words["facts"]) == len(english["facts"]), code
        assert all(shot["title"].count('class="brand"') == 1 for shot in words["shots"].values()), code


def test_each_listing_keeps_to_partner_centers_limits():
    english = (LOCALIZATION / "en.md").read_text(encoding="utf-8")
    disclaimer = re.search(r"^NOT AN OFFICIAL.*$", english, re.M).group(0)
    for path in LOCALIZATION.glob("*.md"):
        listing = path.read_text(encoding="utf-8")
        description = field(listing, "Description")
        features = field(listing, "Product features").splitlines()
        keywords = field(listing, "Keywords").splitlines()

        assert len(description) <= 10_000, path.stem
        assert description.endswith(disclaimer), path.stem
        assert len(field(listing, "What's new in this version")) <= 1500, path.stem
        assert len(field(listing, "Short description")) <= 270, path.stem
        assert len(features) <= 20 and all(len(feature) <= 200 for feature in features), path.stem
        assert len(keywords) <= 7 and all(len(keyword) <= 40 for keyword in keywords), path.stem
        assert sum(len(keyword.split()) for keyword in keywords) <= 21, path.stem
        assert len(field(listing, "Additional system requirements")) <= 200, path.stem
        for shared in ("Copyright and trademark info", "Additional license terms", "Developed by"):
            assert field(listing, shared) == field(english, shared), path.stem


def test_the_games_name_appears_only_in_the_disclaimer_the_trademark_credit_and_the_repos_address():
    # The Store has turned down submissions that used it: see SUBMISSION.md.
    from citygen.gui import server

    texts = [path.read_text(encoding="utf-8") for path in LOCALIZATION.glob("*.md")]
    texts += [path.read_text(encoding="utf-8") for path in (server.STATIC / "i18n").glob("*.json")]
    texts.append((LISTING / "generator" / "captions.js").read_text(encoding="utf-8"))

    for text in texts:
        for allowed in ("not an official minecraft product", "minecraft is a trademark", "chengmarc/minecraft-citygen"):
            text = text.lower().replace(allowed, "")
        assert "minecraft" not in text


def test_every_screenshot_comes_from_a_recorded_scene():
    import sys

    sys.path.insert(0, str(LISTING / "generator"))
    try:
        from capture_windows import SHOTS
    finally:
        sys.path.pop(0)
    recorded = json.loads((LISTING / "generator" / "scenes.json").read_text(encoding="utf-8"))

    assert tuple(SHOTS) == load_render_script().SHOTS
    assert {name for name, _tab, _height in SHOTS.values()} == set(recorded)


def load_replay():
    import sys

    sys.path.insert(0, str(LISTING / "generator"))
    try:
        import replay_scenes
    finally:
        sys.path.pop(0)
    return replay_scenes


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' own windows")
def test_a_window_of_the_apps_name_counts_as_the_app_unless_file_explorer_owns_it(monkeypatch):
    import ctypes
    from ctypes import wintypes

    replay_scenes = load_replay()
    create = ctypes.windll.user32.CreateWindowExW
    create.restype = wintypes.HWND
    create.argtypes = (
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    )
    window = create(0, "STATIC", replay_scenes.APP_NAME, 0, 0, 0, 0, 0, None, None, None, None)   # never shown
    assert window
    try:
        assert replay_scenes.app_is_open()
        monkeypatch.setattr(replay_scenes, "_window_program", lambda _hwnd: "explorer.exe")
        assert not replay_scenes.app_is_open()
    finally:
        ctypes.windll.user32.DestroyWindow.argtypes = (wintypes.HWND,)
        ctypes.windll.user32.DestroyWindow(window)


def test_the_cities_are_not_rebuilt_under_an_open_app(monkeypatch):
    replay_scenes = load_replay()
    monkeypatch.setattr(replay_scenes, "app_is_open", lambda: True)
    monkeypatch.setattr(replay_scenes, "replay", lambda *_args: pytest.fail("it replayed"))
    monkeypatch.setattr(replay_scenes.files, "clear_pipeline_artifacts", lambda: pytest.fail("it cleared appdata"))

    with pytest.raises(SystemExit, match="Close"):
        replay_scenes.main(["promo"])


def test_the_readme_shows_the_english_screenshots_git_tracks(tmp_path, monkeypatch):
    render = load_render_script()
    monkeypatch.setattr(render, "LISTING", tmp_path)
    english = tmp_path / "en"
    english.mkdir()
    for number, shot in enumerate(render.SHOTS, 1):
        (english / f"screenshot-{number}-{shot}.png").write_bytes(shot.encode())

    render.copy_readme_screenshots(english, tmp_path / "screenshots")

    copied = sorted(path.name for path in (tmp_path / "screenshots").iterdir())
    assert copied == ["screenshot-1-promo.png", "screenshot-2-size.png", "screenshot-3-styles.png"]
    readme = (LISTING.parent / "README.md").read_text(encoding="utf-8")
    assert [name for name in copied if f"docs/screenshots/{name}" in readme] == copied


def load_recorder():
    spec = importlib.util.spec_from_file_location("record_scene", LISTING / "generator" / "record_scene.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def fresh_config():
    from citygen.gui.extract_tab import default_extraction_tab_config
    from citygen.gui.form import default_state

    return {"algo": {**default_state(), "seed": "7"}, "extraction": default_extraction_tab_config()}


def test_a_default_city_is_recorded_as_its_seed_alone():
    assert load_recorder().scene_of(fresh_config()) == {"seed": "7"}


def test_a_city_records_only_what_differs_from_a_fresh_install():
    config = fresh_config()
    config["algo"]["algo"]["FINE"] = "40"
    config["extraction"]["house"] = {"start": [1, 64, 2], "end": [3, 65, 4]}
    config["extraction"]["world_path"] = "C:/mc/medieval"

    assert load_recorder().scene_of(config) == {
        "seed": "7",
        "algo": {"FINE": "40"},
        "world": "C:/mc/medieval",
        "areas": {"house": {"start": [1, 64, 2], "end": [3, 65, 4]}},
    }


def test_packaging_mirrors_the_app_name_from_config():
    # The build script and installer don't import citygen.paths, so they repeat the
    # name; a rename that misses one ships an installer for a missing .exe.
    from citygen.paths import APP_NAME

    build = load_build_script()
    iss = (Path(__file__).resolve().parents[1] / "packaging" / "windows_installer.iss").read_text(encoding="utf-8")

    assert (build.APP_NAME, build.MSIX_DISPLAY_NAME) == (APP_NAME, APP_NAME)
    assert f'#define AppName "{APP_NAME}"' in iss
    assert f'Filename: "{{app}}\\{APP_NAME}.exe"' in iss
