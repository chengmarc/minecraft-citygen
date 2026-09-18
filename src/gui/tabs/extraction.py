"""Extraction tab: source-world regions and asset extraction."""

from __future__ import annotations

import threading

from PySide6 import QtWidgets

from config.path import BUILDS_CONTACT_SHEET, ROADS_CONTACT_SHEET, has_region_files
from config.world import BlockRegion, BuildRegion, detect_world_data_version, release_name_for
from pipeline import services, stages

from gui.core import app_files, extraction_config, progress
from gui.core.workers import ProgressMixin, start_background_job
from gui.tabs.control import ExtractionControlPanel
from gui.widgets.qt_viewer import QtImageViewer
from gui.widgets.region_dialog import RegionSelectorDialog

EXTRACT_PHASE_INDEX = {
    (stage, phase): index
    for index, (stage, phase, _weight) in enumerate(progress.EXTRACTION_PHASE_WEIGHTS)
}
EXTRACT_PHASE_WEIGHT_VALUES = [weight for _stage, _phase, weight in progress.EXTRACTION_PHASE_WEIGHTS]

EXTRACT_STATUS_LABELS = {
    (stages.ROADS_EXTRACT, "scan"): "Scanning road region",
    (stages.ROADS_EXTRACT, "export"): "Extracting road pieces",
    (stages.ROADS_RENDER, "render"): "Building road contact sheet",
    (stages.BUILDS_EXTRACT, "scan"): "Scanning build regions",
    (stages.BUILDS_EXTRACT, "export"): "Extracting building pieces",
    (stages.BUILDS_RENDER, "render"): "Building asset sheet",
}

def _extract_phase(stage, label):
    if stage in (stages.ROADS_EXTRACT, stages.BUILDS_EXTRACT):
        return "scan" if (label or "").startswith("Scanning") else "export"
    return "render"


def coalesce_pipeline_progress(emit, *, buckets=100):
    """Reduce redundant cross-thread progress events while preserving completion."""
    last_key = None

    def on_progress(stage, completed, total, label):
        nonlocal last_key
        total_i = max(int(total), 1)
        completed_i = max(0, min(int(completed), total_i))
        bucket = buckets if completed_i >= total_i else int((completed_i * buckets) / total_i)
        key = (stage, _extract_phase(stage, label), total_i, bucket)
        if key == last_key:
            return
        last_key = key
        emit(stage, float(completed_i), float(total_i), label)

    return on_progress


class ExtractionTab(QtWidgets.QWidget, ProgressMixin):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self._init_progress_mixin()
        self._extract_timing = progress.ProgressTimingRecorder()
        state = owner.get_saved_config_section("extraction") or extraction_config.default_extraction_tab_config()
        app_files.clear_preview_cache()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(0)
        viewer_shell = QtWidgets.QWidget(self)
        viewer_row = QtWidgets.QHBoxLayout(viewer_shell)
        viewer_row.setContentsMargins(0, 0, 0, 0)
        viewer_row.setSpacing(12)
        self.road_viewer = QtImageViewer(
            "Road Pieces Found",
            "Extract assets to scan the selected road sample area and build a road contact sheet.",
            viewer_shell,
        )
        self.road_viewer.image_path = ROADS_CONTACT_SHEET
        self.build_viewer = QtImageViewer(
            "Building Pieces Found",
            "Extract assets to scan the selected house and landmark areas and build a building contact sheet.",
            viewer_shell,
        )
        self.build_viewer.image_path = BUILDS_CONTACT_SHEET
        viewer_row.addWidget(self.road_viewer, 1)
        viewer_row.addWidget(self.build_viewer, 1)
        layout.addWidget(viewer_shell, 1)
        layout.addSpacing(20)

        self.controls = ExtractionControlPanel(state, self)
        self.world_edit = self.controls.world_edit
        self.browse_button = self.controls.browse_button
        self.detected_version_edit = self.controls.detected_version_edit
        self.version_combo = self.controls.version_combo
        self.extract_button = self.controls.extract_button
        self.road_group = self.controls.road_group
        self.house_group = self.controls.house_group
        self.landmark_group = self.controls.landmark_group
        self.controls.browse_requested.connect(self._browse_world)
        self.controls.extract_requested.connect(self._run_extract_all)
        self.controls.set_pick_commands(
            road=lambda: self._open_region_selector(self.road_group, "road", "Road Region Selector"),
            house=lambda: self._open_region_selector(self.house_group, "house", "House Region Selector"),
            landmark=lambda: self._open_region_selector(self.landmark_group, "landmark", "Landmark Region Selector"),
        )

        self.controls.connect_change_handler(self._save_state)
        self.world_edit.textChanged.connect(self._refresh_detected_version)
        self.road_group.connect_change_handler(self._refresh_extract_readiness)
        self.house_group.connect_change_handler(self._refresh_extract_readiness)
        self.landmark_group.connect_change_handler(self._refresh_extract_readiness)
        layout.addWidget(self.controls)

        layout.addSpacing(8)
        self.status_label = QtWidgets.QLabel("", self)
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, progress.PROGRESS_BAR_SCALE)
        layout.addWidget(self.progress_bar)

        self._refresh_detected_version()
        self._refresh_extract_readiness()

    def _save_state(self):
        self.owner.set_saved_config_section("extraction", self._current_config_state())
        if hasattr(self.owner, "note_extraction_inputs_changed"):
            self.owner.note_extraction_inputs_changed()

    def prerequisite_state(self):
        state = self._current_config_state()
        return {
            "world_path": state["world_path"],
            "road": state["road"],
            "house": state["house"],
            "landmark": state["landmark"],
        }

    def _select_version(self, value):
        self.controls.select_version(value)

    def _refresh_detected_version(self):
        path = self.world_edit.text().strip()
        version = detect_world_data_version(path) if path else None
        text = release_name_for(version) if version is not None else ""
        self.detected_version_edit.setText(text)
        fm = self.detected_version_edit.fontMetrics()
        measure = text if text else self.detected_version_edit.placeholderText()
        self.detected_version_edit.setFixedWidth(fm.horizontalAdvance(measure) + 20)
        self._rebuild_version_combo(version)
        self._refresh_extract_readiness()

    def _world_is_ready(self):
        path = self.world_edit.text().strip()
        return bool(path) and has_region_files(path)

    def _areas_are_ready(self):
        return all(
            group.has_selection()
            for group in (self.road_group, self.house_group, self.landmark_group)
        )

    def _refresh_extract_readiness(self):
        world_ready = self._world_is_ready()
        self.controls.set_world_ready(world_ready)
        self.controls.set_extract_enabled(world_ready and self._areas_are_ready())

    def _rebuild_version_combo(self, min_data_version):
        self.controls.rebuild_version_combo(min_data_version)

    def _current_config_state(self):
        return {
            "world_path": self.world_edit.text().strip(),
            "target_version": self.version_combo.currentData() or extraction_config.AUTO_VERSION,
            "road": self._serialize_group_state(self.road_group, "Road"),
            "house": self._serialize_group_state(self.house_group, "House"),
            "landmark": self._serialize_group_state(self.landmark_group, "Landmark"),
        }

    def _serialize_group_state(self, group, label):
        if not group.has_selection():
            return {"start": None, "end": None}
        start, end = group.get_xyz_pair(label)
        return {"start": list(start), "end": list(end)}

    def _default_xyz_pair(self, key):
        defaults = extraction_config.default_extraction_tab_config()
        region_state = defaults[key]
        return tuple(region_state["start"]), tuple(region_state["end"])

    def _browse_world(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Minecraft World Folder",
            self.world_edit.text().strip() or "",
        )
        if not folder:
            return
        if not has_region_files(folder):
            QtWidgets.QMessageBox.warning(
                self,
                "Not a Minecraft world",
                f"No region files (.mca) were found in:\n{folder}\n\n"
                "Please select a valid Minecraft world folder.",
            )
            return
        self.world_edit.setText(folder)
        self.controls.clear_area_selections()
        app_files.clear_pipeline_artifacts()
        self.road_viewer.set_message(
            "Extract assets to scan the selected road sample area and build a road contact sheet."
        )
        self.build_viewer.set_message(
            "Extract assets to scan the selected house and landmark areas and build a building contact sheet."
        )
        self._save_state()
        self._refresh_extract_readiness()

    def _open_region_selector(self, group, key, title):
        save_path = self.world_edit.text().strip()
        if not self._world_is_ready():
            QtWidgets.QMessageBox.critical(
                self,
                "Missing world path",
                "Choose a valid Minecraft world before selecting an area on the map.",
            )
            return
        label = {"road": "Road", "house": "House", "landmark": "Landmark"}[key]
        if group.has_selection():
            try:
                start, end = group.get_xyz_pair(label)
            except ValueError as exc:
                QtWidgets.QMessageBox.critical(self, "Invalid extraction region", str(exc))
                return
        else:
            start, end = self._default_xyz_pair(key)

        dialog = RegionSelectorDialog(
            self,
            title=title,
            save_path=save_path,
            start_xyz=start,
            end_xyz=end,
            on_apply=lambda new_start, new_end: group.set_xyz_pair(new_start, new_end),
        )
        if dialog.exec():
            self._save_state()
            self._refresh_extract_readiness()

    def _record_extract_timing(self, stage, phase, completed, total, label):
        self._extract_timing.record(stage, completed, total, label, phase=phase)

    def _finish_extract_timing(self):
        def phase_key(event):
            if event["stage"] == stages.ROADS_EXTRACT:
                prefix = "roads"
            elif event["stage"] == stages.ROADS_RENDER:
                prefix = "roads"
            elif event["stage"] == stages.BUILDS_EXTRACT:
                prefix = "builds"
            elif event["stage"] == stages.BUILDS_RENDER:
                prefix = "builds"
            else:
                return None
            return f"{prefix}_{event['phase']}"

        app_files.save_progress_timing(
            "extraction",
            self._extract_timing.finish(
                phase_key=phase_key,
                weights={
                    f"{stage}:{phase}": weight
                    for stage, phase, weight in progress.EXTRACTION_PHASE_WEIGHTS
                },
            ),
        )

    def _on_pipeline_progress(self, stage, completed, total, label):
        phase = _extract_phase(stage, label)
        self._record_extract_timing(stage, phase, completed, total, label)
        phase_index = EXTRACT_PHASE_INDEX[(stage, phase)]
        seg_end = progress.weighted_segment(
            EXTRACT_PHASE_WEIGHT_VALUES,
            phase_index,
            progress.PROGRESS_BAR_SCALE,
        )[1]
        total_f = float(total) if total > 0 else 1.0
        completed_f = max(0.0, min(float(completed), total_f))
        frac = completed_f / total_f
        target = progress.weighted_item_milestone(
            EXTRACT_PHASE_WEIGHT_VALUES,
            phase_index,
            completed_f,
            total_f,
            progress.PROGRESS_BAR_SCALE,
        )
        status = EXTRACT_STATUS_LABELS.get((stage, phase), "Extracting assets")
        self._cancel_progress_animation()

        if frac >= 1.0:
            self.progress_bar.setValue(int(round(seg_end)))
            self._progress_soft_target = float(seg_end)
            self.set_status(status)
            return

        milestone = max(self.progress_bar.value(), int(round(target)))
        self.progress_bar.setValue(milestone)

        next_target = progress.weighted_item_milestone(
            EXTRACT_PHASE_WEIGHT_VALUES,
            phase_index,
            completed_f + 1.0,
            total_f,
            progress.PROGRESS_BAR_SCALE,
        )
        self._progress_soft_target = progress.soft_target(milestone, next_target, "extraction")
        self._progress_timer.start(progress.creep_tick_ms("extraction"))
        self.set_status(status)

    def _run_extract_all(self):
        try:
            state = self._current_config_state()
        except ValueError as exc:
            QtWidgets.QMessageBox.critical(self, "Invalid extraction region", str(exc))
            return

        env = {"MC_CITY_SAVE": state["world_path"].strip()}
        env.update(extraction_config.stamp_version_env(state["world_path"].strip()))
        road_start, road_end = self.road_group.get_xyz_pair("Road")
        env["MC_CITY_ROAD_BOX"] = BlockRegion.from_xyz_pair(road_start, road_end).to_env_value()
        house_start, house_end = self.house_group.get_xyz_pair("House")
        landmark_start, landmark_end = self.landmark_group.get_xyz_pair("Landmark")
        env["MC_CITY_BUILD_TYPES"] = ";".join(
            [
                BuildRegion(1, BlockRegion.from_xyz_pair(house_start, house_end)).to_env_value(),
                BuildRegion(2, BlockRegion.from_xyz_pair(landmark_start, landmark_end)).to_env_value(),
            ]
        )

        if hasattr(self.owner, "begin_extraction_run"):
            self.owner.begin_extraction_run()
        run_state = self.prerequisite_state()
        self._save_state()
        self.extract_button.setEnabled(False)
        self.set_status("Preparing extraction")
        self.progress_bar.setRange(0, progress.PROGRESS_BAR_SCALE)
        self.progress_bar.setValue(0)
        self._progress_soft_target = 0.0
        self._extract_timing.start()

        succeeded = False

        def _handle_success(run_state):
            nonlocal succeeded
            succeeded = True
            self._handle_extract_success(run_state)

        def _handle_finished():
            self._stop_progress()
            if hasattr(self.owner, "end_extraction_run"):
                self.owner.end_extraction_run(succeeded)
            self._refresh_extract_readiness()

        def job(emit_progress):
            on_progress = coalesce_pipeline_progress(emit_progress)
            services.run_stage("roads", env_overrides=env, progress=on_progress)
            services.run_stage("builds", env_overrides=env, progress=on_progress)
            return run_state

        start_background_job(
            self,
            job,
            on_progress=self._on_pipeline_progress,
            on_success=_handle_success,
            on_finished=_handle_finished,
            failure_title="Extract failed",
            failure_status="Extract failed",
            thread_factory=threading.Thread,
        )

    def _handle_extract_success(self, run_state):
        self.road_viewer.load_image(self.road_viewer.image_path)
        self.build_viewer.load_image(self.build_viewer.image_path)
        self._finish_extract_timing()
        self._finish_progress()
        self.set_status("Extraction complete")
        if hasattr(self.owner, "mark_extraction_complete"):
            self.owner.mark_extraction_complete(run_state)
