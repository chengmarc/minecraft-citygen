"""Preview and Build: one shared algorithm form, Stage 3 for the preview, Stages 4 then 5 for the build.

Both tabs edit the same saved ``algo`` section, so the city you preview is the one you build.
"""

from __future__ import annotations

import os
import random

from config.path import SAVES, city_preview_path, city_render_path, grid_preview_path
from config.world import SAVE, source_data_version
from pipeline import services, stages

from gui.core import algo_config, app_files, progress
from gui.web.server import file_url

PREVIEW_STEPS = {step.module: (index, step.label) for index, step in enumerate(stages.STAGES["preview"])}

BUILD_STATUS_LABELS = {
    stages.CITY_CONSTRUCT: "Building city layout",
    stages.CITY_RENDER: "Rendering final city",
    stages.WORLD_EXPORT: "Exporting MC world",
}

SEED_MAX = 2_147_483_647


def form_spec():
    """The algorithm form the page builds: header selectors and the advanced groups."""
    selectors = [
        {
            "name": name,
            "label": algo_config.PREVIEW_CONFIG_LOOKUP[name][0],
            "description": algo_config.PREVIEW_CONFIG_LOOKUP[name][1],
            "options": list(options),
        }
        for name, (options, _human) in algo_config.SELECTOR_OPTIONS.items()
    ]
    groups = []
    for title, names in algo_config.PREVIEW_CONFIG_GROUPS:
        fields = []
        for name in names:
            label, description = algo_config.PREVIEW_CONFIG_LOOKUP[name]
            field = {"name": name, "label": label, "description": description}
            if name == "BANNED_BUILDINGS":
                field.update(kind="text", placeholder="e.g. 001, 002")
            else:
                minimum, maximum = algo_config.PREVIEW_SLIDER_RANGES.get(name, (-99999, 99999))
                field.update(kind="slider", min=minimum, max=maximum)
            fields.append(field)
        groups.append({"title": title, "fields": fields})
    return {"selectors": selectors, "groups": groups}


def preview_progress(stage, completed, total):
    """``(value, soft_target, status)`` for a Stage 3 step, in PROGRESS_BAR_SCALE units."""
    step_index, step_label = PREVIEW_STEPS[stage]
    total_f = float(total) if total > 0 else 1.0
    completed_f = max(0.0, min(float(completed), total_f))

    def milestone(done):
        return progress.weighted_item_milestone(
            progress.PREVIEW_STEP_WEIGHTS, step_index, done, total_f, progress.PROGRESS_BAR_SCALE,
        )

    value = milestone(completed_f)
    soft_target = None
    if completed_f < total_f:
        soft_target = progress.soft_target(value, milestone(completed_f + 1.0), "preview")
    return value, soft_target, step_label


def build_progress(stage, completed, total, label=""):
    """``(value, soft_target, status)`` for a Stage 4 or 5 step, in PROGRESS_BAR_SCALE units.

    Construction names the step it's starting in ``label``; the status shows it.
    """
    scale = progress.PROGRESS_BAR_SCALE
    construct_weights = progress.GENERATION_CONSTRUCT_WEIGHTS
    weights = progress.GENERATION_WEIGHTS
    n = int(completed)
    status = BUILD_STATUS_LABELS.get(stage, "Building city")
    if stage == stages.CITY_CONSTRUCT and label and n < len(construct_weights):
        status = label

    if stage == stages.CITY_CONSTRUCT:
        value = progress.weighted_milestone(weights, n, scale)
        soft_target = None
        if n < len(construct_weights):
            next_value = progress.weighted_milestone(weights, n + 1, scale)
            soft_target = progress.soft_target(value, next_value, "generation")
        return value, soft_target, status

    segment = len(construct_weights) if stage == stages.CITY_RENDER else len(construct_weights) + 1
    t = float(total) if total > 0 else 1.0
    value = progress.weighted_item_milestone(weights, segment, n, t, scale)
    soft_target = None
    if n < total:
        next_value = progress.weighted_item_milestone(weights, segment, n + 1, t, scale)
        soft_target = progress.soft_target(value, next_value, "generation")
    return value, soft_target, status


def _new_seed(current_seed):
    seed = str(random.randint(0, SEED_MAX))
    while seed == current_seed:
        seed = str(random.randint(0, SEED_MAX))
    return seed


def _image(path):
    url = file_url(path)
    return {"src": url} if url else {"message": f"Image not found:\n{path}"}


def _build_timing_key(event):
    return {
        stages.CITY_CONSTRUCT: "construct",
        stages.CITY_RENDER: "render",
        stages.WORLD_EXPORT: "export",
    }.get(event["stage"])


class AlgoTabs:
    """The Preview and Build tabs' calls."""

    def __init__(self, settings, runner):
        self._settings = settings
        self._runner = runner

    def state(self):
        saved = self._settings.get("algo") or algo_config.default_algo_tab_config()
        return {**saved, "algo": algo_config.create_config_values(saved.get("algo"))}

    def save(self, state):
        self._settings.set("algo", state)

    def reset(self):
        state = algo_config.default_algo_tab_config()
        self.save(state)
        return state

    def _algo(self, state, title):
        try:
            return algo_config.build_algo_from_values(algo_config.create_config_values(state.get("algo"))), None
        except algo_config.ConfigError as exc:
            return None, {"title": title, "message": str(exc)}

    def run_preview(self, state):
        """Pick a fresh seed and start Stage 3; returns the saved state, or the error to show."""
        if self._runner.is_running("preview"):
            return {"error": {"title": "Preview running", "message": "A preview is already running."}}
        state = {**state, "seed": _new_seed(str(state.get("seed", "")).strip())}
        self.save(state)
        algo, error = self._algo(state, "Invalid preview config")
        if error:
            return {"error": error}
        seed = state["seed"]

        def job(report):
            def on_progress(stage, completed, total, _label):
                report(*preview_progress(stage, completed, total), creep="preview")

            services.run_stage("preview", seed=seed, algo=algo, progress=on_progress)
            return seed

        self._runner.start(
            "preview", job,
            failure_title="Preview failed",
            status="Preparing preview",
            on_success=lambda seed: {
                "images": {"grid": _image(grid_preview_path(seed)), "city": _image(city_preview_path(seed))},
                "status": "Preview ready",
            },
        )
        return {"state": state}

    def run_build(self, state):
        """Start Stage 4 then Stage 5 with the previewed seed, from the source world chosen on Extract."""
        if self._runner.is_running("build"):
            return {"error": {"title": "Build running", "message": "A build is already running."}}
        self.save(state)
        seed = str(state.get("seed", "")).strip()
        try:
            algo_config.validate_seed(seed)
        except algo_config.SeedError as exc:
            return {"error": {"title": "Invalid seed", "message": str(exc)}}
        algo, error = self._algo(state, "Invalid city config")
        if error:
            return {"error": error}
        save = str((self._settings.get("extraction") or {}).get("world_path", SAVE))
        data_version = source_data_version(save)
        timing = progress.ProgressTimingRecorder()
        timing.start()

        def job(report):
            def on_progress(stage, completed, total, label):
                timing.record(stage, completed, total, label)
                report(*build_progress(stage, completed, total, label))

            services.run_stage("city", seed=seed, algo=algo, data_version=data_version, progress=on_progress)
            services.run_stage("world", seed=seed, save=save, progress=on_progress)
            return seed

        def on_success(seed):
            app_files.save_progress_timing("generation", timing.finish(
                phase_key=_build_timing_key,
                weights={
                    "construct": list(progress.GENERATION_CONSTRUCT_WEIGHTS),
                    "render": progress.GENERATION_RENDER_WEIGHT,
                    "export": progress.GENERATION_WORLD_WEIGHT,
                },
            ))
            return {"images": {"city": _image(city_render_path(seed))}, "status": "Build complete"}

        self._runner.start("build", job, failure_title="Generation failed", status="Building city layout",
                           on_success=on_success)
        return {}

    def open_worlds_folder(self):
        """Open the exported-worlds folder so the user can copy a world into saves/."""
        os.makedirs(SAVES, exist_ok=True)
        try:
            app_files.open_in_file_manager(SAVES)
        except OSError as exc:
            return {"error": {"title": "Could not open worlds folder", "message": str(exc)}}
        return {}
