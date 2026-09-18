"""Preview tab: fast road-grid and city-layout PNG generation."""

from __future__ import annotations

import random
import threading

from PySide6 import QtWidgets

from config.path import city_preview_path, grid_preview_path
from pipeline import services, stages

from gui.core import algo_config, progress
from gui.core.workers import ProgressMixin, start_background_job
from gui.tabs._algo import AlgoTabMixin
from gui.widgets.qt_viewer import QtImageViewer
from gui.widgets.widgets import AlgoControlsWidget


PREVIEW_STEPS = {step.module: (index, step.label) for index, step in enumerate(stages.STAGES["preview"])}


class PreviewTab(QtWidgets.QWidget, AlgoTabMixin, ProgressMixin):
    legacy_state_sections = ("preview",)
    ready_tooltip = "Generate a fast road and city layout preview."

    def __init__(self, owner):
        super().__init__(owner)
        self._init_algo_tab(owner)
        self._init_progress_mixin()
        state = self._load_algo_state()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(0)
        viewer_shell = QtWidgets.QWidget(self)
        viewer_row = QtWidgets.QHBoxLayout(viewer_shell)
        viewer_row.setContentsMargins(0, 0, 0, 0)
        viewer_row.setSpacing(12)
        self.grid_viewer = QtImageViewer(
            "Road Layout Preview",
            "Preview layout to see the road network before building the final city.",
            viewer_shell,
        )
        self.city_viewer = QtImageViewer(
            "City Layout Preview",
            "Preview layout to see how buildings fit into the generated road network.",
            viewer_shell,
        )
        viewer_row.addWidget(self.grid_viewer, 1)
        viewer_row.addWidget(self.city_viewer, 1)
        layout.addWidget(viewer_shell, 1)
        layout.addSpacing(20)

        self.controls = AlgoControlsWidget(
            "Preview",
            self._randomize_seed_and_run_preview,
            state,
            action_icon_name="refresh.png",
            extra_actions=[("Reset", self._reset_defaults, "reset.png")],
            show_seed=False,
            parent=self,
        )
        self.controls.connect_change_handler(self._save_algo_state)
        layout.addWidget(self.controls)

        layout.addSpacing(8)
        self.status_label = QtWidgets.QLabel("", self)
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        self.refresh_prerequisite_state()

    def _preview_milestone(self, step_index, completed, total):
        return progress.weighted_item_milestone(
            progress.PREVIEW_STEP_WEIGHTS,
            step_index,
            completed,
            total,
            self.progress_bar.maximum(),
        )

    def _on_pipeline_progress(self, stage, completed, total, _label):
        step_index, step_label = PREVIEW_STEPS[stage]
        total_f = float(total) if total > 0 else 1.0
        completed_f = max(0.0, min(float(completed), total_f))
        milestone = max(
            self.progress_bar.value(),
            int(round(self._preview_milestone(step_index, completed_f, total_f))),
        )
        self._cancel_progress_animation()
        self.progress_bar.setValue(milestone)
        if completed_f < total_f:
            next_ms = self._preview_milestone(step_index, completed_f + 1.0, total_f)
            self._progress_soft_target = progress.soft_target(milestone, next_ms, "preview")
            self._progress_timer.start(progress.creep_tick_ms("preview"))
        self.set_status(step_label)

    def _reset_defaults(self):
        self.controls.set_state(algo_config.default_algo_tab_config())
        self._save_algo_state()

    def _randomize_seed_and_run_preview(self):
        current_seed = self.controls.seed_edit.text().strip()
        seed = str(random.randint(0, 2_147_483_647))
        while seed == current_seed:
            seed = str(random.randint(0, 2_147_483_647))
        self.controls.seed_edit.setText(seed)
        self._run_preview()

    def _run_preview(self):
        seed = self.controls.seed_edit.text().strip()
        try:
            algo_config.validate_seed(seed)
            algo = algo_config.build_algo_from_values(self.controls.algo_values())
        except algo_config.SeedError as exc:
            QtWidgets.QMessageBox.critical(self, "Invalid seed", str(exc))
            return
        except algo_config.ConfigError as exc:
            QtWidgets.QMessageBox.critical(self, "Invalid preview config", str(exc))
            return

        self._start_progress()
        self.controls.action_button.setEnabled(False)
        self.set_status("Preparing preview")

        def handle_success(seed):
            self._load_previews(seed)
            self._finish_progress()
            self.set_status("Preview ready")

        def handle_finished():
            self._stop_progress()
            self.refresh_prerequisite_state()

        def job(on_progress):
            services.run_stage("preview", seed=seed, algo=algo, progress=on_progress)
            return seed

        start_background_job(
            self,
            job,
            on_progress=self._on_pipeline_progress,
            on_failed=self.show_failure,
            on_success=handle_success,
            on_finished=handle_finished,
            failure_title="Preview failed",
            failure_status="Preview failed",
            thread_factory=threading.Thread,
        )

    def _load_previews(self, seed):
        self.grid_viewer.load_image(grid_preview_path(seed))
        self.city_viewer.load_image(city_preview_path(seed))
