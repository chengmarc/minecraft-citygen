"""Preview and Build: the algorithm form, Stage 3 for the preview, Stages 4 then 5 for the build.

Each knob of the form names one :class:`config.algo.Algo` field, upper-cased. Both tabs edit the same saved
``algo`` section, so the city you preview is the one you build.
"""

from __future__ import annotations

import os
import random
from dataclasses import replace

from config.algo import ALGO, DEFAULT_SEED
from config.env import parse_set
from config.path import SAVES, city_preview_path, city_render_path, grid_preview_path
from config.world import source_data_version
from pipeline import services, stages

from gui import files, progress
from gui.server import image


# --- The form: which knobs show, and how their values become an ``Algo``

class ConfigError(ValueError):
    """Raised when an algorithm/city config value is invalid."""


PREVIEW_CONFIGS = [
    ("FINE", "City size", "Changes the footprint of the finished city."),
    ("GAP_MIXED", "Road density", "Controls how tightly Avenues and Streets are packed across the city."),
    ("GAP_BIG", "Avenue spacing", "Higher values create fewer Avenues."),
    ("PAD_BIG", "Avenue edge margin", "Keeps Avenues farther from the edge of the city."),
    ("GAP_SMALL", "Street spacing", "Lower values create more Streets."),
    ("PAD_SMALL", "Street edge margin", "Keeps Streets farther from the edge of the city."),
    ("N_BIG_CORNERS", "Avenue turns", "Adds more bends to Avenues."),
    ("N_BIG_TEES", "Avenue T-junctions", "Adds more T-junctions to Avenues."),
    ("N_SMALL_CORNERS", "Street turns", "Adds more bends to Streets."),
    ("N_SMALL_TEES", "Street T-junctions", "Adds more T-junctions to Streets."),
    ("BANNED_BUILDINGS", "Skip building IDs", "Optional comma-separated building IDs to leave out of generation."),
    ("TYPE1_TOP_FIT_CHOICES", "House style variety", "Higher values mix in more different standard house designs."),
    ("LANDMARK_SPACING", "Landmark spacing", "Minimum fine-cell distance between landmark footprints."),
]

PREVIEW_CONFIG_LOOKUP = {name: (label, description) for name, label, description in PREVIEW_CONFIGS}

PREVIEW_CONFIG_GROUPS = [
    ("Avenue and Street spacing", ["GAP_BIG", "PAD_BIG", "GAP_SMALL", "PAD_SMALL"]),
    ("Avenue and Street shape", ["N_BIG_CORNERS", "N_BIG_TEES", "N_SMALL_CORNERS", "N_SMALL_TEES"]),
    ("Building mix", ["TYPE1_TOP_FIT_CHOICES", "LANDMARK_SPACING", "BANNED_BUILDINGS"]),
]

PREVIEW_SLIDER_RANGES = {
    "GAP_BIG": (2, 10),
    "GAP_SMALL": (2, 10),
    "PAD_BIG": (2, 10),
    "PAD_SMALL": (2, 10),
    "N_BIG_CORNERS": (0, 10),
    "N_SMALL_CORNERS": (0, 10),
    "N_BIG_TEES": (0, 10),
    "N_SMALL_TEES": (0, 10),
    "TYPE1_TOP_FIT_CHOICES": (1, 10),
    "LANDMARK_SPACING": (1, 10),
}

CANVAS_SIZE_OPTIONS = {
    "Very Small": "40",
    "Small": "60",
    "Normal": "80",
    "Big": "100",
    "Very Big": "120",
}

CLEARANCE_OPTIONS = {
    "Very Dense": "3",
    "Dense": "4",
    "Normal": "5",
    "Sparse": "6",
    "Very Sparse": "7",
}

# Config values the header row exposes as labelled selectors rather than raw
# integers. Maps config name -> (label->value options, human-facing name).
SELECTOR_OPTIONS = {
    "FINE": (CANVAS_SIZE_OPTIONS, "City size"),
    "GAP_MIXED": (CLEARANCE_OPTIONS, "Road density"),
}


def selector_value(name, label):
    """Resolve a selector label (e.g. 'Small') to its numeric config value."""
    options, human = SELECTOR_OPTIONS[name]
    try:
        return options[label]
    except KeyError as exc:
        raise ConfigError(f"{human} must be one of the selector values.") from exc


def selector_label(name, value):
    """Resolve a numeric config value back to its selector label, or None."""
    options, _human = SELECTOR_OPTIONS[name]
    for label, numeric in options.items():
        if str(value) == numeric:
            return label
    return None


def config_default(name):
    value = getattr(ALGO, name.lower())
    if isinstance(value, frozenset):
        return ", ".join(sorted(value))
    if name in SELECTOR_OPTIONS:
        label = selector_label(name, value)
        if label is not None:
            return label
    return str(value)


def form_values(saved=None):
    """Every knob's value as text: the saved one, else the default."""
    return {
        name: str(saved[name]).strip() if saved and name in saved else config_default(name)
        for name, _label, _description in PREVIEW_CONFIGS
    }


def build_algo_from_values(values):
    """The :class:`config.algo.Algo` that :func:`form_values` describes."""
    knobs = {}
    for name, _label, _description in PREVIEW_CONFIGS:
        value = values[name]
        if name == "BANNED_BUILDINGS":
            knobs[name.lower()] = frozenset(parse_set(value))
            continue
        if name in SELECTOR_OPTIONS:
            value = selector_value(name, value)
        try:
            knobs[name.lower()] = int(value)
        except ValueError as exc:
            raise ConfigError(f"{name} must be an integer.") from exc
    return replace(ALGO, **knobs)


def default_algo_tab_config():
    return {
        "seed": str(DEFAULT_SEED),
        "algo": form_values(),
    }


# --- The tabs

SEED_MAX = 2_147_483_647


def form_spec():
    """The algorithm form the page builds: header selectors and the advanced groups."""
    selectors = [
        {
            "name": name,
            "label": PREVIEW_CONFIG_LOOKUP[name][0],
            "description": PREVIEW_CONFIG_LOOKUP[name][1],
            "options": list(options),
        }
        for name, (options, _human) in SELECTOR_OPTIONS.items()
    ]
    groups = []
    for title, names in PREVIEW_CONFIG_GROUPS:
        fields = []
        for name in names:
            label, description = PREVIEW_CONFIG_LOOKUP[name]
            field = {"name": name, "label": label, "description": description}
            if name == "BANNED_BUILDINGS":
                field.update(kind="text", placeholder="e.g. 001, 002")
            else:
                minimum, maximum = PREVIEW_SLIDER_RANGES.get(name, (-99999, 99999))
                field.update(kind="slider", min=minimum, max=maximum)
            fields.append(field)
        groups.append({"title": title, "fields": fields})
    return {"selectors": selectors, "groups": groups}


def _new_seed(current_seed):
    seed = str(random.randint(0, SEED_MAX))
    while seed == current_seed:
        seed = str(random.randint(0, SEED_MAX))
    return seed


class AlgoTabs:
    """The Preview and Build tabs' calls. An error is ``{"error": {"code", "detail"}}``, which the page words.

    ``world_path()`` is the source world chosen on Extract, which the build writes the city into.
    """

    def __init__(self, settings, runner, *, world_path):
        self._settings = settings
        self._runner = runner
        self._world_path = world_path

    def state(self):
        saved = self._settings.get("algo") or default_algo_tab_config()
        return {**saved, "algo": form_values(saved.get("algo"))}

    def save(self, state):
        self._settings.set("algo", state)

    def reset(self):
        state = default_algo_tab_config()
        self.save(state)
        return state

    def _algo(self, state):
        try:
            return build_algo_from_values(form_values(state.get("algo"))), None
        except ConfigError as exc:
            return None, {"code": "invalid_config", "detail": str(exc)}

    def run_preview(self, state):
        """Pick a fresh seed and start Stage 3; returns the saved state, or the error to show."""
        if self._runner.is_running("preview"):
            return {"error": {"code": "running"}}
        state = {**state, "seed": _new_seed(str(state.get("seed", "")).strip())}
        self.save(state)
        algo, error = self._algo(state)
        if error:
            return {"error": error}
        seed = state["seed"]

        def job(report):
            def on_progress(stage, completed, total, _label):
                report(*progress.preview_progress(stage, completed, total))
                if stage == stages.PREVIEW_GRID and total and completed >= total:   # ready well before the city
                    self._runner.show("preview", {"grid": image(grid_preview_path(seed))})

            services.run_stage("preview", seed=seed, algo=algo, progress=on_progress)
            return seed

        self._runner.start("preview", job, on_success=lambda seed: {
            "images": {"grid": image(grid_preview_path(seed)), "city": image(city_preview_path(seed))},
        })
        return {"state": state}

    def run_build(self, state):
        """Start Stage 4 then Stage 5 with the previewed seed, from the source world chosen on Extract."""
        if self._runner.is_running("build"):
            return {"error": {"code": "running"}}
        self.save(state)
        seed = str(state.get("seed", "")).strip()
        try:
            int(seed)
        except ValueError:
            return {"error": {"code": "invalid_seed", "detail": "Seed must be an integer."}}
        algo, error = self._algo(state)
        if error:
            return {"error": error}
        save = self._world_path()
        data_version = source_data_version(save)
        timing = progress.ProgressTimingRecorder("build")

        def job(report):
            def on_progress(stage, completed, total, label):
                timing.record(stage, completed, total, label)
                report(*progress.build_progress(stage, completed, total, label))

            services.run_stage("city", seed=seed, algo=algo, data_version=data_version, progress=on_progress)
            services.run_stage("world", seed=seed, save=save, progress=on_progress)
            return seed

        def on_success(seed):
            files.save_progress_timing("build", timing.finish())
            return {"images": {"city": image(city_render_path(seed))}}

        self._runner.start("build", job, on_success=on_success)
        # The city as previewed, standing in until it's rendered (if this seed's preview is still there).
        blueprint = image(city_preview_path(seed))
        if "src" in blueprint:
            self._runner.show("build", {"city": {**blueprint, "blueprint": True}})
        return {}

    def open_worlds_folder(self):
        """Open the exported-worlds folder so the user can copy a world into saves/."""
        os.makedirs(SAVES, exist_ok=True)
        try:
            files.open_in_file_manager(SAVES)
        except OSError as exc:
            return {"error": {"code": "worlds_folder", "detail": str(exc)}}
        return {}
