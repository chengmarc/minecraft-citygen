"""Build the cities in scenes.json again, without the app, and keep their pictures in build/scenes/<name>/.

Each runs Extract, Preview and the Build's construction and render with the recorded values; no world is exported, as
the screenshots only need the pictures. Like the app's launch, this clears appdata/ but for the exported worlds and the
saved settings, so it refuses to run with the app open.

render.py runs this for any city whose pictures are missing. Run it yourself after changing the pipeline or a city:
python store-listing/generator/replay_scenes.py [name ...]
"""

from __future__ import annotations

import ctypes
import json
import shutil
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from citygen import step1_extract, step2_preview, step3_build   # noqa: E402
from citygen.gui import files   # noqa: E402
from citygen.gui.form import build_algo, form_values   # noqa: E402
from citygen.paths import (   # noqa: E402
    APP_NAME, BUILDS_CONTACT_SHEET, city_preview_path, city_render_path, DEFAULT_WORLD, grid_preview_path,
    ROADS_CONTACT_SHEET,
)
from citygen.settings import BlockRegion, BuildRegion, SAMPLE_AREAS   # noqa: E402
from citygen.tools.world_reader import source_data_version   # noqa: E402

GENERATOR = Path(__file__).resolve().parent
SCENES = GENERATOR / "scenes.json"
PICTURES = GENERATOR.parents[1] / "build" / "scenes"


def _window_program(hwnd):
    """The name of the program that owns window ``hwnd``, in lower case, or "" if Windows won't say."""
    process_id = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = wintypes.HANDLE
    process = kernel32.OpenProcess(0x1000, False, process_id.value)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not process:
        return ""
    path = ctypes.create_unicode_buffer(1024)
    size = wintypes.DWORD(len(path))
    kernel32.QueryFullProcessImageNameW(wintypes.HANDLE(process), 0, path, ctypes.byref(size))
    kernel32.CloseHandle(wintypes.HANDLE(process))
    return Path(path.value).name.lower()


def app_is_open():
    """Whether the app's window is up. Its title bar doesn't draw the title, but the window keeps it.

    File Explorer titles a window after its folder, so a folder named like the app doesn't count. Any other window of
    that name does, even one whose owner Windows won't name: better to refuse than to clear appdata/ under the app.
    """
    if sys.platform != "win32":
        return False
    find = ctypes.windll.user32.FindWindowExW
    find.restype = wintypes.HWND
    find.argtypes = (wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR)
    hwnd = find(None, None, None, APP_NAME)
    while hwnd:
        if _window_program(hwnd) != "explorer.exe":
            return True
        hwnd = find(None, hwnd, None, APP_NAME)
    return False


def regions(scene):
    """The scene's road box and build regions: its own areas, else a fresh install's."""
    areas = {key: (tuple(start), tuple(end)) for key, (start, end) in SAMPLE_AREAS.items()}
    for key, area in scene.get("areas", {}).items():
        areas[key] = (tuple(area["start"]), tuple(area["end"]))
    road_box = BlockRegion.from_xyz_pair(*areas["road"])
    build_types = (
        BuildRegion(1, BlockRegion.from_xyz_pair(*areas["house"])),
        BuildRegion(2, BlockRegion.from_xyz_pair(*areas["landmark"])),
    )
    return road_box, build_types


def replay(name, scene):
    """Build one scene, and return where its pictures are."""
    seed = int(scene["seed"])
    save = scene.get("world", DEFAULT_WORLD)
    algo = build_algo(form_values(scene.get("algo")))
    road_box, build_types = regions(scene)

    def quiet(*_report):
        pass

    files.clear_pipeline_artifacts()
    step1_extract.run(save, road_box, build_types, quiet)
    step2_preview.run(seed, algo, quiet)
    step3_build.construct(seed, algo, source_data_version(save), quiet)
    step3_build.render(seed)

    folder = PICTURES / name
    folder.mkdir(parents=True, exist_ok=True)
    pictures = {
        "roads": ROADS_CONTACT_SHEET,
        "builds": BUILDS_CONTACT_SHEET,
        "grid": grid_preview_path(seed),
        "city-preview": city_preview_path(seed),
        "city-render": city_render_path(seed),
    }
    for picture, source in pictures.items():
        shutil.copyfile(source, folder / f"{picture}.png")
    return folder


def main(names):
    if app_is_open():
        raise SystemExit(f"Close {APP_NAME} first: rebuilding the cities clears appdata/ underneath it.")
    scenes = json.loads(SCENES.read_text(encoding="utf-8"))
    for name in names or scenes:
        started = time.perf_counter()
        folder = replay(name, scenes[name])
        print(f"{name}: {time.perf_counter() - started:.0f}s, {folder}", flush=True)
    files.clear_pipeline_artifacts()


if __name__ == "__main__":
    main(sys.argv[1:])
