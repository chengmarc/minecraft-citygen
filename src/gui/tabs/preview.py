"""Preview tab: fast road-grid and city-layout PNG generation."""

from __future__ import annotations

import random
import threading

from PySide6 import QtWidgets

from pipeline import services

from gui.core import common, progress
from gui.core.workers import ProgressMixin, WorkerSignals
from gui.tabs._algo import AlgoTabMixin
from gui.widgets.qt_viewer import QtImageViewer
from gui.widgets.widgets import AlgoControlsWidget


class PreviewTab(QtWidgets.QWidget, AlgoTabMixin, ProgressMixin):
    legacy_state_sections = ("preview",)
    prerequisite_owner_method = "preview_prerequisite_met"
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

    def _preview_milestone(self, completed):
        return progress.weighted_milestone(
            progress.PREVIEW_STEP_WEIGHTS,
            completed,
            self.progress_bar.maximum(),
        )

    def _on_pipeline_progress(self, _stage, completed, total, label):
        total_i = max(int(total), 1)
        completed_i = max(0, min(int(completed), total_i))
        milestone = self._preview_milestone(completed_i)
        self._cancel_progress_animation()
        self.progress_bar.setValue(milestone)
        if completed_i < min(total_i, len(progress.PREVIEW_STEP_WEIGHTS)):
            next_ms = self._preview_milestone(completed_i + 1)
            self._progress_soft_target = progress.soft_target(milestone, next_ms, "preview")
            self._progress_timer.start(progress.creep_tick_ms("preview"))
        self.set_status(label or "Generating previews")

    def _reset_defaults(self):
        self.controls.set_state(common.default_algo_tab_config())
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
            common.validate_seed(seed)
            env = common.build_algo_env_from_values(self.controls.algo_values())
            fine = env["MC_CITY_FINE"]
        except common.SeedError as exc:
            QtWidgets.QMessageBox.critical(self, "Invalid seed", str(exc))
            return
        except common.ConfigError as exc:
            QtWidgets.QMessageBox.critical(self, "Invalid preview config", str(exc))
            return

        if hasattr(self.owner, "begin_preview_run"):
            self.owner.begin_preview_run()
        run_state = self.controls.current_state()

        self._start_progress()
        self.controls.action_button.setEnabled(False)
        self.set_status("Preparing preview")

        signals = WorkerSignals(self)
        signals.pipeline_progress.connect(self._on_pipeline_progress)
        signals.failed.connect(self._show_failure)
        signals.success.connect(lambda payload: (
            self._load_previews(payload),
            self._finish_progress(),
            self.set_status("Preview ready"),
        ))
        signals.finished.connect(lambda: (self._stop_progress(), self.refresh_prerequisite_state()))

        def on_progress(stage, completed, total, label):
            signals.pipeline_progress.emit(stage, float(completed), float(total), label or "")

        def worker():
            try:
                services.run_preview_stage(seed, fine, env_overrides=env, progress=on_progress)
            except Exception as exc:  # boundary: surface any background failure to the UI
                signals.failed.emit("Preview failed", str(exc).strip() or "Preview failed", "Preview failed")
            else:
                signals.success.emit((seed, run_state))
            finally:
                signals.finished.emit()

        threading.Thread(target=worker, daemon=True).start()

    def _load_previews(self, payload):
        seed, run_state = payload
        self.grid_viewer.load_image(common.grid_preview_path(seed))
        self.city_viewer.load_image(common.city_preview_path(seed))
        if hasattr(self.owner, "mark_preview_complete"):
            self.owner.mark_preview_complete(run_state)
