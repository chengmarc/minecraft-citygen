"""Preview and Build: the algorithm form, Stage 3 for the preview, Stages 4 then 5 for the build.

Each knob of the form names one :class:`config.algo.Algo` field, upper-cased, and its value is text, as the page sends
it. The form's words -- each knob's label and tip, the groups' names, the selectors' option names -- are in the page's
text.js, keyed by the codes here. Both tabs edit the same saved ``algo`` section, so the city you preview is the one
you build.
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
    """A knob's value is invalid. Its message is the knob's name, which the page words."""


# Every knob, in the order the form's values are kept.
KNOBS = [
    "FINE",
    "GAP_MIXED",
    "GAP_BIG",
    "PAD_BIG",
    "GAP_SMALL",
    "PAD_SMALL",
    "N_BIG_CORNERS",
    "N_BIG_TEES",
    "N_SMALL_CORNERS",
    "N_SMALL_TEES",
    "BANNED_BUILDINGS",
    "TYPE1_TOP_FIT_CHOICES",
    "LANDMARK_SPACING",
]

# The header's selectors: knobs chosen from a few values, which text.js names.
SELECTOR_OPTIONS = {
    "FINE": ("40", "60", "80", "100", "120"),
    "GAP_MIXED": ("3", "4", "5", "6", "7"),
}

# The advanced panel's groups, by code; it builds fields only for grouped knobs.
GROUPS = [
    ("spacing", ["GAP_BIG", "PAD_BIG", "GAP_SMALL", "PAD_SMALL"]),
    ("shape", ["N_BIG_CORNERS", "N_BIG_TEES", "N_SMALL_CORNERS", "N_SMALL_TEES"]),
    ("buildings", ["TYPE1_TOP_FIT_CHOICES", "LANDMARK_SPACING", "BANNED_BUILDINGS"]),
]

SLIDER_RANGES = {
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

# Knobs typed as text: a comma-separated set, which becomes a ``frozenset`` field.
SET_KNOBS = {"BANNED_BUILDINGS"}


def _default(name):
    value = getattr(ALGO, name.lower())
    return ", ".join(sorted(value)) if isinstance(value, frozenset) else str(value)


def form_values(saved=None):
    """Every knob's value: the saved one, else the default.

    A selector's saved value that isn't one of its options is dropped, as are the option labels older versions saved.
    """
    values = {}
    for name in KNOBS:
        value = str(saved[name]).strip() if saved and name in saved else None
        if value is None or (name in SELECTOR_OPTIONS and value not in SELECTOR_OPTIONS[name]):
            value = _default(name)
        values[name] = value
    return values


def build_algo(values):
    """The :class:`config.algo.Algo` that :func:`form_values` describes; raises :class:`ConfigError`."""
    knobs = {}
    for name in KNOBS:
        value = values[name]
        if name in SET_KNOBS:
            knobs[name.lower()] = frozenset(parse_set(value))
            continue
        if name in SELECTOR_OPTIONS and value not in SELECTOR_OPTIONS[name]:
            raise ConfigError(name)
        try:
            knobs[name.lower()] = int(value)
        except ValueError as exc:
            raise ConfigError(name) from exc
    return replace(ALGO, **knobs)


def default_state():
    """The Preview and Build tabs' saved state as a fresh install has it."""
    return {"seed": str(DEFAULT_SEED), "algo": form_values()}


def form_spec():
    """The form the page builds: the header's selectors and the advanced panel's groups."""

    def field(name):
        if name in SET_KNOBS:
            return {"name": name, "kind": "text"}
        minimum, maximum = SLIDER_RANGES.get(name, (-99999, 99999))
        return {"name": name, "kind": "slider", "min": minimum, "max": maximum}

    return {
        "selectors": [{"name": name, "options": list(options)} for name, options in SELECTOR_OPTIONS.items()],
        "groups": [{"code": code, "fields": [field(name) for name in names]} for code, names in GROUPS],
    }


# --- The tabs

SEED_MAX = 2_147_483_647


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
        saved = self._settings.get("algo") or default_state()
        return {**saved, "algo": form_values(saved.get("algo"))}

    def save(self, state):
        self._settings.set("algo", state)

    def reset(self):
        state = default_state()
        self.save(state)
        return state

    def _algo(self, state):
        try:
            return build_algo(form_values(state.get("algo"))), None
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
            return {"error": {"code": "invalid_seed"}}
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
