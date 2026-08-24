"""Generation tab: production schematic, render, and world export."""

from __future__ import annotations

import os
import threading

from PySide6 import QtWidgets

from config.path import SAVES
from config.world import SAVE
from pipeline import services

from gui.core import common
from gui.core.workers import ProgressMixin, WorkerSignals
from gui.tabs._progress import GENERATION_STAGE_STEPS, GENERATION_TOTAL_STEPS, PROGRESS_BAR_SCALE
from gui.widgets.qt_viewer import QtImageViewer
from gui.widgets.widgets import AlgoControlsWidget

GENERATION_STATUS_LABELS = {
    services.CITY_CONSTRUCT: "Building city layout",
    services.CITY_RENDER: "Rendering final city",
    services.WORLD_EXPORT: "Exporting Minecraft world",
}


class GenerationTab(QtWidgets.QWidget, ProgressMixin):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self._peer = None
        self._init_progress_mixin()
        state = (
            owner.get_saved_config_section("algo")
            or owner.get_saved_config_section("render")
            or common.default_algo_tab_config()
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(0)
        self.city_viewer = QtImageViewer(
            "Final City Render",
            "Use Build City to create the schematic, the render, and the exported Minecraft world.",
            self,
        )
        layout.addWidget(self.city_viewer, 1)
        layout.addSpacing(20)

        self.controls = AlgoControlsWidget(
            "Build City",
            self._run_generate,
            state,
            action_icon_name="render.png",
            extra_actions=[("Copy World", self._open_output_folder, "folder.png")],
            parent=self,
        )
        self.controls.connect_change_handler(self._save_state)
        layout.addWidget(self.controls)

        layout.addSpacing(8)
        self.status_label = QtWidgets.QLabel("", self)
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, PROGRESS_BAR_SCALE)
        layout.addWidget(self.progress_bar)
        self.refresh_prerequisite_state()

    def set_peer(self, peer):
        self._peer = peer

    def current_run_state(self):
        return self.controls.current_state()

    def refresh_prerequisite_state(self):
        ready = True
        if hasattr(self.owner, "generation_prerequisite_met"):
            ready = bool(self.owner.generation_prerequisite_met())
        self.controls.action_button.setEnabled(ready)
        self.controls.action_button.setToolTip(
            "Complete Extract Assets first." if not ready else "Build the final schematic, render, and export world."
        )

    def _save_state(self):
        state = self.controls.current_state()
        self.owner.set_saved_config_section("algo", state)
        if self._peer is not None:
            self._peer.controls.set_state(state)
        if hasattr(self.owner, "note_preview_inputs_changed"):
            self.owner.note_preview_inputs_changed()

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

    def _on_pipeline_progress(self, stage, completed, total, label):
        n = int(completed)
        c_weights = common.GENERATION_CONSTRUCT_WEIGHTS
        r_weight = common.GENERATION_RENDER_WEIGHT
        w_weight = common.GENERATION_WORLD_WEIGHT
        scale = float(sum(c_weights) + r_weight + w_weight)

        def bar(weight_prefix):
            return int(round(weight_prefix / scale * PROGRESS_BAR_SCALE))

        self._cancel_progress_animation()

        if stage == services.CITY_CONSTRUCT:
            milestone = bar(sum(c_weights[:n]))
            self.progress_bar.setValue(milestone)
            if n < len(c_weights):
                next_ms = bar(sum(c_weights[:n]) + c_weights[n])
                self._progress_soft_target = milestone + int(
                    (next_ms - milestone) * common.SCRIPT_PROGRESS_HEADROOM
                )
                self._progress_timer.start(common.SCRIPT_PROGRESS_TICK_MS)
        else:
            if stage == services.CITY_RENDER:
                seg_start, seg_weight = sum(c_weights), r_weight
            else:
                seg_start, seg_weight = sum(c_weights) + r_weight, w_weight
            bar_start = bar(seg_start)
            seg_span = bar(seg_start + seg_weight) - bar_start
            t = float(total) if total > 0 else 1.0
            milestone = bar_start + int(round(n / t * seg_span))
            self.progress_bar.setValue(milestone)
            if n < total:
                next_ms = bar_start + int(round((n + 1) / t * seg_span))
                self._progress_soft_target = milestone + int(
                    (next_ms - milestone) * common.SCRIPT_PROGRESS_HEADROOM
                )
                self._progress_timer.start(common.SCRIPT_PROGRESS_TICK_MS)

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
        self.progress_bar.setRange(0, PROGRESS_BAR_SCALE)
        self.progress_bar.setValue(0)

        signals = WorkerSignals(self)
        signals.pipeline_progress.connect(self._on_pipeline_progress)
        signals.failed.connect(self._show_failure)
        signals.success.connect(lambda payload: (
            self.city_viewer.load_image(common.city_render_path(payload)),
            self._finish_progress(),
            self.set_status("Build complete"),
        ))
        signals.finished.connect(lambda: (self._stop_progress(), self.refresh_prerequisite_state()))

        def on_progress(stage, completed, total, label):
            signals.pipeline_progress.emit(stage, float(completed), float(total), label or "")

        def worker():
            try:
                services.run_city_construct_stage(seed, fine, env_overrides=env, progress=on_progress)
                services.run_city_render_stage(env_overrides=env, progress=on_progress)
                services.run_world_export_stage(seed, env_overrides=env, progress=on_progress)
            except Exception as exc:  # boundary: surface any background failure to the UI
                signals.failed.emit("Generation failed", str(exc).strip() or "Generation failed", "Generation failed")
            else:
                signals.success.emit(seed)
            finally:
                signals.finished.emit()

        threading.Thread(target=worker, daemon=True).start()
