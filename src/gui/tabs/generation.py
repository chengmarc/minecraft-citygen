"""Generation tab: production schematic, render, and world export."""

from __future__ import annotations

import os
import threading

from PySide6 import QtWidgets

from config.path import SAVES
from config.world import SAVE
from pipeline import services

from gui.core import common, progress
from gui.core.workers import ProgressMixin, start_background_job
from gui.tabs._algo import AlgoTabMixin
from gui.tabs.control import GenerationControlPanel
from gui.widgets.qt_viewer import QtImageViewer

GENERATION_STATUS_LABELS = {
    services.CITY_CONSTRUCT: "Building city layout",
    services.CITY_RENDER: "Rendering final city",
    services.WORLD_EXPORT: "Exporting Minecraft world",
}


class GenerationTab(QtWidgets.QWidget, AlgoTabMixin, ProgressMixin):
    legacy_state_sections = ("render",)
    prerequisite_owner_method = "generation_prerequisite_met"
    ready_tooltip = "Build the final schematic, render, and export world."

    def __init__(self, owner):
        super().__init__(owner)
        self._init_algo_tab(owner)
        self._init_progress_mixin()
        self._generation_timing = progress.ProgressTimingRecorder()
        state = self._load_algo_state()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(0)
        self.city_viewer = QtImageViewer(
            "Final City Render",
            "Build city to create the schematic, the render, and the exported Minecraft world.",
            self,
        )
        layout.addWidget(self.city_viewer, 1)
        layout.addSpacing(20)

        self.controls = GenerationControlPanel(state, self._run_generate, self._open_output_folder, self)
        self.controls.connect_change_handler(self._save_algo_state)
        layout.addWidget(self.controls)

        layout.addSpacing(8)
        self.status_label = QtWidgets.QLabel("", self)
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, progress.PROGRESS_BAR_SCALE)
        layout.addWidget(self.progress_bar)
        self.refresh_prerequisite_state()

    def _source_env(self):
        """Env pinning the source world for the render pipeline.

        MC_CITY_SAVE lets the world-export stage read the source world's own
        level.dat as the base for the exported world. The version stamp keeps the
        schematic on the source version so outputs stay aligned with the source.
        """
        extraction = self.owner.get_saved_config_section("extraction") or {}
        world_path = str(extraction.get("world_path", SAVE))
        return {"MC_CITY_SAVE": world_path, **common.stamp_version_env(world_path)}

    def _open_output_folder(self):
        """Open the exported-worlds folder so the user can copy a world into saves/."""
        os.makedirs(SAVES, exist_ok=True)
        try:
            common.open_in_file_manager(SAVES)
        except OSError as exc:
            QtWidgets.QMessageBox.critical(self, "Could not open worlds folder", str(exc))

    def _record_generation_timing(self, stage, completed, total, label):
        self._generation_timing.record(stage, completed, total, label)

    def _finish_generation_timing(self):
        def phase_key(event):
            if event["stage"] == services.CITY_CONSTRUCT:
                return "construct"
            if event["stage"] == services.CITY_RENDER:
                return "render"
            if event["stage"] == services.WORLD_EXPORT:
                return "export"
            return None

        common.save_progress_timing(
            "generation",
            self._generation_timing.finish(
                phase_key=phase_key,
                weights={
                    "construct": list(progress.GENERATION_CONSTRUCT_WEIGHTS),
                    "render": progress.GENERATION_RENDER_WEIGHT,
                    "export": progress.GENERATION_WORLD_WEIGHT,
                },
            ),
        )

    def _on_pipeline_progress(self, stage, completed, total, label):
        self._record_generation_timing(stage, completed, total, label)
        n = int(completed)
        c_weights = progress.GENERATION_CONSTRUCT_WEIGHTS
        weights = c_weights + [progress.GENERATION_RENDER_WEIGHT, progress.GENERATION_WORLD_WEIGHT]

        self._cancel_progress_animation()

        if stage == services.CITY_CONSTRUCT:
            milestone = progress.weighted_milestone(weights, n, progress.PROGRESS_BAR_SCALE)
            self.progress_bar.setValue(milestone)
            if n < len(c_weights):
                next_ms = progress.weighted_milestone(weights, n + 1, progress.PROGRESS_BAR_SCALE)
                self._progress_soft_target = progress.soft_target(milestone, next_ms, "generation")
                self._progress_timer.start(progress.creep_tick_ms("generation"))
        else:
            if stage == services.CITY_RENDER:
                segment_index = len(c_weights)
            else:
                segment_index = len(c_weights) + 1
            t = float(total) if total > 0 else 1.0
            milestone = int(round(progress.weighted_item_milestone(
                weights,
                segment_index,
                n,
                t,
                progress.PROGRESS_BAR_SCALE,
            )))
            self.progress_bar.setValue(milestone)
            if n < total:
                next_ms = progress.weighted_item_milestone(
                    weights,
                    segment_index,
                    n + 1,
                    t,
                    progress.PROGRESS_BAR_SCALE,
                )
                self._progress_soft_target = progress.soft_target(milestone, next_ms, "generation")
                self._progress_timer.start(progress.creep_tick_ms("generation"))

        self.set_status(GENERATION_STATUS_LABELS.get(stage, "Building city"))

    def _run_generate(self):
        seed = self.controls.seed_edit.text().strip()
        try:
            common.validate_seed(seed)
            env = common.build_algo_env_from_values(self.controls.algo_values())
            fine = env["MC_CITY_FINE"]
        except common.SeedError as exc:
            QtWidgets.QMessageBox.critical(self, "Invalid seed", str(exc))
            return
        except common.ConfigError as exc:
            QtWidgets.QMessageBox.critical(self, "Invalid city config", str(exc))
            return

        env.update(self._source_env())

        self.controls.action_button.setEnabled(False)
        self.set_status("Building city layout")
        self.progress_bar.setRange(0, progress.PROGRESS_BAR_SCALE)
        self.progress_bar.setValue(0)
        self._generation_timing.start()

        def handle_success(payload):
            self.city_viewer.load_image(common.city_render_path(payload))
            self._finish_generation_timing()
            self._finish_progress()
            self.set_status("Build complete")

        def handle_finished():
            self._stop_progress()
            self.refresh_prerequisite_state()

        def job(on_progress):
            services.run_city_stage(seed, fine, env_overrides=env, progress=on_progress)
            services.run_world_stage(seed, env_overrides=env, progress=on_progress)
            return seed

        start_background_job(
            self,
            job,
            on_progress=self._on_pipeline_progress,
            on_success=handle_success,
            on_finished=handle_finished,
            failure_title="Generation failed",
            failure_status="Generation failed",
            thread_factory=threading.Thread,
        )
