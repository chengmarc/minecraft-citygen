"""Preview and Build: Stage 3 for the preview, Stages 4 then 5 for the build.

Both tabs edit the same saved ``algo`` section through the form (:mod:`gui.form`), so the city you preview is the one
you build.
"""

from __future__ import annotations

import os
import random

from config.path import SAVES, city_preview_path, city_render_path, grid_preview_path
from config.world import source_data_version
from pipeline import services, stages

from gui import files, progress
from gui.form import ConfigError, build_algo, default_state, form_values
from gui.server import image

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

        def job(report):
            def on_progress(stage, completed, total, label):
                report(*progress.build_progress(stage, completed, total, label))

            services.run_stage("city", seed=seed, algo=algo, data_version=data_version, progress=on_progress)
            services.run_stage("world", seed=seed, save=save, progress=on_progress)
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
