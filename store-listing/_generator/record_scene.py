"""Record the city the app just built, so it can be built again without the app.

Three cities make the five screenshots: ``promo`` (1, and 4 and 5 from the same seed), ``size`` (2) and ``styles`` (3).
Each is kept in scenes.json as what sets it apart from a fresh install: its seed, and any settings, areas or world that
differ. The same values make the same city: everything random in the pipeline is drawn from the seed.

Run it from the repo root once the app has started the Build: python store-listing/_generator/record_scene.py promo
The Preview tab picks a new seed on every run, and the Build takes the last one, so record after Build, not before.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from citygen.gui.form import form_values   # noqa: E402
from citygen.paths import DEFAULT_WORLD, SETTINGS   # noqa: E402
from citygen.settings import SAMPLE_AREAS   # noqa: E402

SCENES = Path(__file__).with_name("scenes.json")
NAMES = ("promo", "size", "styles")


def _same_path(first, second):
    return os.path.normcase(os.path.normpath(first)) == os.path.normcase(os.path.normpath(second))


def scene_of(config):
    """What sets the city in the app's saved ``config`` apart from a fresh install's."""
    state = config["algo"]
    extraction = config.get("extraction") or {}
    scene = {"seed": str(state["seed"])}

    knobs = form_values(state.get("algo"))
    defaults = form_values()
    algo = {name: value for name, value in knobs.items() if value != defaults[name]}
    if algo:
        scene["algo"] = algo

    world = extraction.get("world_path", DEFAULT_WORLD)
    if not _same_path(world, DEFAULT_WORLD):
        scene["world"] = world

    areas = {}
    for key, (start, end) in SAMPLE_AREAS.items():
        area = extraction.get(key, {"start": list(start), "end": list(end)})
        if (area["start"], area["end"]) != (list(start), list(end)):
            areas[key] = area
    if areas:
        scene["areas"] = areas
    return scene


def main(name):
    if name not in NAMES:
        raise SystemExit(f"Name one of: {', '.join(NAMES)}.")
    with open(SETTINGS, encoding="utf-8") as fh:
        scene = scene_of(json.load(fh))
    scenes = json.loads(SCENES.read_text(encoding="utf-8")) if SCENES.is_file() else {}
    scenes[name] = scene
    SCENES.write_text(json.dumps(scenes, indent=2) + "\n", encoding="utf-8")
    print(name, json.dumps(scene, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
