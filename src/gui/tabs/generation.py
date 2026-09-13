"""Generation tab: production schematic, render, and world export."""

from __future__ import annotations

import os
import threading
import time

from PySide6 import QtWidgets

from config.path import SAVES
from config.world import SAVE
from pipeline import services

from gui.core import common, progress
from gui.core.workers import ProgressMixin, WorkerSignals
from gui.tabs._algo import AlgoTabMixin
from gui.widgets.qt_viewer import QtImageViewer
from gui.widgets.widgets import AlgoControlsWidget

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
        self._generation_timing_started_at = None
        self._generation_timing_last = None
        self._generation_timing_events = []
        state = self._load_algo_state()

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
        now = time.perf_counter()
        if self._generation_timing_started_at is None:
            self._generation_timing_started_at = now

        completed_i = int(completed)
        total_i = int(total)
        label = label or ""
        key = (stage, completed_i, total_i, label)
        last = self._generation_timing_last
        if last is not None and last["key"] != key:
            self._generation_timing_events.append(
                {
                    "stage": last["stage"],
                    "completed": last["completed"],
                    "total": last["total"],
                    "label": last["label"],
                    "seconds": round(now - last["time"], 4),
                }
            )
        if last is None or last["key"] != key:
            self._generation_timing_last = {
                "key": key,
                "stage": stage,
                "completed": completed_i,
                "total": total_i,
                "label": label,
                "time": now,
            }

    def _finish_generation_timing(self):
        now = time.perf_counter()
        last = self._generation_timing_last
        if last is not None:
            self._generation_timing_events.append(
                {
                    "stage": last["stage"],
                    "completed": last["completed"],
                    "total": last["total"],
                    "label": last["label"],
                    "seconds": round(now - last["time"], 4),
                }
            )
        started_at = self._generation_timing_started_at or now
        phase_seconds = {"construct": 0.0, "render": 0.0, "export": 0.0}
        for event in self._generation_timing_events:
            if event["stage"] == services.CITY_CONSTRUCT:
                phase = "construct"
            elif event["stage"] == services.CITY_RENDER:
                phase = "render"
            elif event["stage"] == services.WORLD_EXPORT:
                phase = "export"
            else:
                continue
            phase_seconds[phase] += event["seconds"]
        payload = {
            "total_seconds": round(now - started_at, 4),
            "phase_seconds": {key: round(value, 4) for key, value in phase_seconds.items()},
            "weights": {
                "construct": list(progress.GENERATION_CONSTRUCT_WEIGHTS),
                "render": progress.GENERATION_RENDER_WEIGHT,
                "export": progress.GENERATION_WORLD_WEIGHT,
            },
            "events": self._generation_timing_events,
        }
        common.save_progress_timing("generation", payload)
        self._generation_timing_started_at = None
        self._generation_timing_last = None
        self._generation_timing_events = []

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
        self._generation_timing_started_at = time.perf_counter()
        self._generation_timing_last = None
        self._generation_timing_events = []

        signals = WorkerSignals(self)
        signals.pipeline_progress.connect(self._on_pipeline_progress)
        signals.failed.connect(self._show_failure)
        signals.success.connect(lambda payload: (
            self.city_viewer.load_image(common.city_render_path(payload)),
            self._finish_generation_timing(),
            self._finish_progress(),
            self.set_status("Build complete"),
        ))
        signals.finished.connect(lambda: (self._stop_progress(), self.refresh_prerequisite_state()))

        def on_progress(stage, completed, total, label):
            signals.pipeline_progress.emit(stage, float(completed), float(total), label or "")

        def worker():
            try:
                services.run_city_stage(seed, fine, env_overrides=env, progress=on_progress)
                services.run_world_stage(seed, env_overrides=env, progress=on_progress)
            except Exception as exc:  # boundary: surface any background failure to the UI
                signals.failed.emit("Generation failed", str(exc).strip() or "Generation failed", "Generation failed")
            else:
                signals.success.emit(seed)
            finally:
                signals.finished.emit()

        threading.Thread(target=worker, daemon=True).start()
