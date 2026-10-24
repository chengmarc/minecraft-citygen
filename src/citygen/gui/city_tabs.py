"""The Preview and Build tabs: each runs its job (citygen.step2_preview, citygen.step3_build) with the form's settings.

Both tabs edit the same saved ``algo`` section through the form (:mod:`citygen.gui.form`), so the city you preview is
the one you build.
"""

from __future__ import annotations

import os
import random

from citygen import step2_preview, step3_build
from citygen.gui import files, progress
from citygen.gui.form import build_algo, ConfigError, default_state, form_values
from citygen.gui.server import image
from citygen.paths import city_preview_path, city_render_path, grid_preview_path, SAVES

SEED_MAX = 2_147_483_647


def _new_seed(current_seed):
    seed = str(random.randint(0, SEED_MAX))
    while seed == current_seed:
        seed = str(random.randint(0, SEED_MAX))
    return seed


class CityTabs:
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
        """Pick a fresh seed and start the preview; returns the saved state, or the error to show."""
        if self._runner.is_running("preview"):
            return {"error": {"code": "running"}}
        state = {**state, "seed": _new_seed(str(state.get("seed", "")).strip())}
        self.save(state)
        algo, error = self._algo(state)
        if error:
            return {"error": error}
        seed = state["seed"]

        def job(report):
            def on_progress(step, completed, total):
                report(*progress.bar("preview", step, completed, total))
                if step == "road_layout" and completed >= total:   # ready well before the city
                    self._runner.show("preview", {"grid": image(grid_preview_path(seed))})

            step2_preview.run(int(seed), algo, on_progress)
            return seed

        self._runner.start("preview", job, on_success=lambda seed: {
            "images": {"grid": image(grid_preview_path(seed)), "city": image(city_preview_path(seed))},
        })
        return {"state": state}

    def run_build(self, state):
        """Start the build with the previewed seed, into a copy of the source world chosen on Extract."""
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

        def job(report):
            def on_progress(step, completed, total, detail=None):
                report(*progress.bar("build", step, completed, total, detail))

            step3_build.run(int(seed), algo, save, on_progress)
            return seed

        self._runner.start("build", job, on_success=lambda seed: {"images": {"city": image(city_render_path(seed))}})
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
