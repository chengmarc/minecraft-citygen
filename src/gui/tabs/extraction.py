"""Extraction tab: source-world regions and asset extraction."""

from __future__ import annotations

import threading
import time

from PySide6 import QtWidgets

from config.path import has_region_files
from config.world import SAVE
from pipeline import services

from gui.core import common
from gui.core.theme import apply_button_icon, style_button
from gui.core.workers import ProgressMixin, WorkerSignals
from gui.tabs._progress import PROGRESS_BAR_SCALE
from gui.widgets.qt_viewer import QtImageViewer
from gui.widgets.region_dialog import RegionSelectorDialog
from gui.widgets.widgets import ExtractionAreaGroup

EXTRACT_PHASE_WEIGHTS = [
    (services.ROADS_EXTRACT, "scan", 3),
    (services.ROADS_EXTRACT, "export", 1),
    (services.ROADS_RENDER, "render", 1),
    (services.BUILDS_EXTRACT, "scan", 80),
    (services.BUILDS_EXTRACT, "export", 10),
    (services.BUILDS_RENDER, "render", 5),
]

EXTRACT_STATUS_LABELS = {
    (services.ROADS_EXTRACT, "scan"): "Scanning road region",
    (services.ROADS_EXTRACT, "export"): "Extracting road pieces",
    (services.ROADS_RENDER, "render"): "Building road contact sheet",
    (services.BUILDS_EXTRACT, "scan"): "Scanning build regions",
    (services.BUILDS_EXTRACT, "export"): "Extracting building pieces",
    (services.BUILDS_RENDER, "render"): "Building asset sheet",
}

_EXTRACT_PHASE_RANGES = {}
_offset = 0
for _stage, _phase, _weight in EXTRACT_PHASE_WEIGHTS:
    _EXTRACT_PHASE_RANGES[(_stage, _phase)] = (_offset, _offset + _weight)
    _offset += _weight
EXTRACT_PHASE_TOTAL = _offset


def _extract_phase(stage, label):
    if stage in (services.ROADS_EXTRACT, services.BUILDS_EXTRACT):
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
        self._extract_timing_started_at = None
        self._extract_timing_last = None
        self._extract_timing_events = []
        state = owner.get_saved_config_section("extraction") or common.default_extraction_tab_config()
        common.clear_preview_cache()

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
        self.road_viewer.image_path = common.ROAD_CONTACT_SHEET
        self.build_viewer = QtImageViewer(
            "Building Pieces Found",
            "Extract assets to scan the selected house and landmark areas and build a building contact sheet.",
            viewer_shell,
        )
        self.build_viewer.image_path = common.BUILD_CONTACT_SHEET
        viewer_row.addWidget(self.road_viewer, 1)
        viewer_row.addWidget(self.build_viewer, 1)
        layout.addWidget(viewer_shell, 1)
        layout.addSpacing(20)

        shell = QtWidgets.QWidget(self)
        shell_layout = QtWidgets.QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)

        header = QtWidgets.QHBoxLayout()
        shell_layout.addLayout(header)
        header.addWidget(QtWidgets.QLabel("Minecraft World"))
        self.world_edit = QtWidgets.QLineEdit(str(state.get("world_path", SAVE)), self)
        self.world_edit.setPlaceholderText("Select a Minecraft world folder")
        self.world_edit.setFixedWidth(420)
        header.addWidget(self.world_edit)
        self.browse_button = QtWidgets.QPushButton("Browse...", self)
        style_button(self.browse_button)
        self.browse_button.setFixedHeight(self.world_edit.sizeHint().height())
        self.browse_button.clicked.connect(self._browse_world)
        header.addWidget(self.browse_button)
        header.addSpacing(12)
        header.addWidget(QtWidgets.QLabel("Source Version"))
        self.detected_version_edit = QtWidgets.QLineEdit(self)
        self.detected_version_edit.setReadOnly(True)
        self.detected_version_edit.setPlaceholderText("-")
        self.detected_version_edit.setToolTip("The Minecraft version of the world you selected.")
        header.addWidget(self.detected_version_edit)
        header.addSpacing(12)
        header.addWidget(QtWidgets.QLabel("Target Version"))
        self.version_combo = QtWidgets.QComboBox(self)
        for label, value in common.version_selector_items():
            self.version_combo.addItem(label, value)
        self._select_version(state.get("target_version", common.AUTO_VERSION))
        self.version_combo.setToolTip(
            "Lets you confirm which Minecraft version you plan to paste into. "
            "CityGen still stamps the exported files to the source world's version."
        )
        header.addWidget(self.version_combo)
        header.addStretch(1)
        self.extract_button = QtWidgets.QPushButton("Extract Assets", self)
        self.extract_button.setObjectName("primaryButton")
        style_button(self.extract_button)
        apply_button_icon(self.extract_button, "extract.png")
        self.extract_button.clicked.connect(self._run_extract_all)
        header.addWidget(self.extract_button)

        shell_layout.addSpacing(10)
        groups = QtWidgets.QHBoxLayout()
        shell_layout.addLayout(groups)
        road_region = self._region_from_state(state.get("road"), area_kind="road")
        house_region = self._region_from_state(state.get("house"), area_kind="house")
        landmark_region = self._region_from_state(state.get("landmark"), area_kind="landmark")
        self.road_group = ExtractionAreaGroup(
            "Road Area",
            "Choose an area that contains the road pieces you want CityGen to reuse.",
            "road",
            road_region,
            self,
        )
        self.house_group = ExtractionAreaGroup(
            "House Area",
            "Choose a sample area with your standard houses or smaller buildings.",
            "house",
            house_region,
            self,
        )
        self.landmark_group = ExtractionAreaGroup(
            "Landmark Area",
            "Choose a sample area with taller or special buildings that should stand out in the city.",
            "landmark",
            landmark_region,
            self,
        )
        self.road_group.set_pick_command(lambda: self._open_region_selector(self.road_group, "road", "Road Region Selector"))
        self.house_group.set_pick_command(lambda: self._open_region_selector(self.house_group, "house", "House Region Selector"))
        self.landmark_group.set_pick_command(
            lambda: self._open_region_selector(self.landmark_group, "landmark", "Landmark Region Selector")
        )
        for group in (self.road_group, self.house_group, self.landmark_group):
            groups.addWidget(group, 1)

        self.world_edit.textChanged.connect(self._save_state)
        self.world_edit.textChanged.connect(self._refresh_detected_version)
        self.version_combo.currentIndexChanged.connect(self._save_state)
        self.road_group.connect_change_handler(self._save_state)
        self.house_group.connect_change_handler(self._save_state)
        self.landmark_group.connect_change_handler(self._save_state)
        self.road_group.connect_change_handler(self._refresh_extract_readiness)
        self.house_group.connect_change_handler(self._refresh_extract_readiness)
        self.landmark_group.connect_change_handler(self._refresh_extract_readiness)
        layout.addWidget(shell)

        layout.addSpacing(8)
        self.status_label = QtWidgets.QLabel("", self)
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, PROGRESS_BAR_SCALE)
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
        index = self.version_combo.findData(value)
        self.version_combo.setCurrentIndex(index if index >= 0 else 0)

    def _refresh_detected_version(self):
        path = self.world_edit.text().strip()
        version = common.detect_world_data_version(path) if path else None
        text = common.release_name_for(version) if version is not None else ""
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
        for group in (self.road_group, self.house_group, self.landmark_group):
            group.set_world_ready(world_ready)
        self.extract_button.setEnabled(world_ready and self._areas_are_ready())

    def _rebuild_version_combo(self, min_data_version):
        current = self.version_combo.currentData()
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        for label, value in common.version_selector_items(min_data_version):
            self.version_combo.addItem(label, value)
        self._select_version(current or common.AUTO_VERSION)
        self.version_combo.blockSignals(False)

    def _current_config_state(self):
        return {
            "world_path": self.world_edit.text().strip(),
            "target_version": self.version_combo.currentData() or common.AUTO_VERSION,
            "road": self._serialize_group_state(self.road_group, "Road"),
            "house": self._serialize_group_state(self.house_group, "House"),
            "landmark": self._serialize_group_state(self.landmark_group, "Landmark"),
        }

    def _serialize_group_state(self, group, label):
        if not group.has_selection():
            return {"start": None, "end": None}
        start, end = group.get_xyz_pair(label)
        return {"start": list(start), "end": list(end)}

    def _region_from_state(self, region_state, *, area_kind):
        if not isinstance(region_state, dict):
            return None
        start = region_state.get("start")
        end = region_state.get("end")
        if not (isinstance(start, list) and isinstance(end, list) and len(start) == 3 and len(end) == 3):
            return None
        bounds = common.BlockRegion.from_xyz_pair(tuple(start), tuple(end))
        if area_kind == "road":
            return bounds
        build_type = 1 if area_kind == "house" else 2
        return common.BuildRegion(build_type, bounds)

    def _default_xyz_pair(self, key):
        defaults = common.default_extraction_tab_config()
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
        for group in (self.road_group, self.house_group, self.landmark_group):
            group.clear_selection()
        common.clear_pipeline_artifacts()
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
        now = time.perf_counter()
        if self._extract_timing_started_at is None:
            self._extract_timing_started_at = now

        completed_i = int(completed)
        total_i = int(total)
        label = label or ""
        key = (stage, phase, completed_i, total_i, label)
        last = self._extract_timing_last
        if last is not None and last["key"] != key:
            self._extract_timing_events.append(
                {
                    "stage": last["stage"],
                    "phase": last["phase"],
                    "completed": last["completed"],
                    "total": last["total"],
                    "label": last["label"],
                    "seconds": round(now - last["time"], 4),
                }
            )
        if last is None or last["key"] != key:
            self._extract_timing_last = {
                "key": key,
                "stage": stage,
                "phase": phase,
                "completed": completed_i,
                "total": total_i,
                "label": label,
                "time": now,
            }

    def _finish_extract_timing(self):
        now = time.perf_counter()
        last = self._extract_timing_last
        if last is not None:
            self._extract_timing_events.append(
                {
                    "stage": last["stage"],
                    "phase": last["phase"],
                    "completed": last["completed"],
                    "total": last["total"],
                    "label": last["label"],
                    "seconds": round(now - last["time"], 4),
                }
            )
        started_at = self._extract_timing_started_at or now
        phase_seconds = {}
        for event in self._extract_timing_events:
            if event["stage"] == services.ROADS_EXTRACT:
                prefix = "roads"
            elif event["stage"] == services.ROADS_RENDER:
                prefix = "roads"
            elif event["stage"] == services.BUILDS_EXTRACT:
                prefix = "builds"
            elif event["stage"] == services.BUILDS_RENDER:
                prefix = "builds"
            else:
                continue
            key = f"{prefix}_{event['phase']}"
            phase_seconds[key] = phase_seconds.get(key, 0.0) + event["seconds"]
        payload = {
            "total_seconds": round(now - started_at, 4),
            "phase_seconds": {key: round(value, 4) for key, value in phase_seconds.items()},
            "weights": {
                f"{stage}:{phase}": weight
                for stage, phase, weight in EXTRACT_PHASE_WEIGHTS
            },
            "events": self._extract_timing_events,
        }
        common.save_progress_timing("extraction", payload)
        self._extract_timing_started_at = None
        self._extract_timing_last = None
        self._extract_timing_events = []

    def _on_pipeline_progress(self, stage, completed, total, label):
        phase = _extract_phase(stage, label)
        self._record_extract_timing(stage, phase, completed, total, label)
        phase_start, phase_end = _EXTRACT_PHASE_RANGES[(stage, phase)]
        seg_start = phase_start / EXTRACT_PHASE_TOTAL * PROGRESS_BAR_SCALE
        seg_end = phase_end / EXTRACT_PHASE_TOTAL * PROGRESS_BAR_SCALE
        seg_span = seg_end - seg_start
        total_f = float(total) if total > 0 else 1.0
        completed_f = max(0.0, min(float(completed), total_f))
        frac = completed_f / total_f
        target = seg_start + frac * seg_span
        status = EXTRACT_STATUS_LABELS.get((stage, phase), "Extracting assets")
        self._cancel_progress_animation()

        if frac >= 1.0:
            self.progress_bar.setValue(int(round(seg_end)))
            self._progress_soft_target = float(seg_end)
            self.set_status(status)
            return

        milestone = max(self.progress_bar.value(), int(round(target)))
        self.progress_bar.setValue(milestone)

        next_frac = min((completed_f + 1.0) / total_f, 1.0)
        next_target = seg_start + next_frac * seg_span
        self._progress_soft_target = milestone + (next_target - milestone) * common.SCRIPT_PROGRESS_HEADROOM
        self._progress_timer.start(common.SCRIPT_PROGRESS_TICK_MS)
        self.set_status(status)

    def _run_extract_all(self):
        try:
            state = self._current_config_state()
        except ValueError as exc:
            QtWidgets.QMessageBox.critical(self, "Invalid extraction region", str(exc))
            return

        env = {"MC_CITY_SAVE": state["world_path"].strip()}
        env.update(common.stamp_version_env(state["world_path"].strip()))
        road_start, road_end = self.road_group.get_xyz_pair("Road")
        env["MC_CITY_ROAD_BOX"] = common.BlockRegion.from_xyz_pair(road_start, road_end).to_env_value()
        house_start, house_end = self.house_group.get_xyz_pair("House")
        landmark_start, landmark_end = self.landmark_group.get_xyz_pair("Landmark")
        env["MC_CITY_BUILD_TYPES"] = ";".join(
            [
                common.BuildRegion(1, common.BlockRegion.from_xyz_pair(house_start, house_end)).to_env_value(),
                common.BuildRegion(2, common.BlockRegion.from_xyz_pair(landmark_start, landmark_end)).to_env_value(),
            ]
        )

        if hasattr(self.owner, "begin_extraction_run"):
            self.owner.begin_extraction_run()
        run_state = self.prerequisite_state()
        self._save_state()
        self.extract_button.setEnabled(False)
        self.set_status("Preparing extraction")
        self.progress_bar.setRange(0, PROGRESS_BAR_SCALE)
        self.progress_bar.setValue(0)
        self._progress_soft_target = 0.0
        self._extract_timing_started_at = time.perf_counter()
        self._extract_timing_last = None
        self._extract_timing_events = []

        signals = WorkerSignals(self)
        run_context = {"succeeded": False}
        signals.pipeline_progress.connect(self._on_pipeline_progress)
        signals.failed.connect(self._show_failure)

        def _handle_success(run_state):
            run_context["succeeded"] = True
            self._handle_extract_success(run_state)

        def _handle_finished():
            self._stop_progress()
            if hasattr(self.owner, "end_extraction_run"):
                self.owner.end_extraction_run(run_context["succeeded"])
            self._refresh_extract_readiness()

        signals.success.connect(_handle_success)
        signals.finished.connect(_handle_finished)

        def worker():
            try:
                on_progress = coalesce_pipeline_progress(
                    lambda stage, completed, total, label: signals.pipeline_progress.emit(stage, completed, total, label)
                )

                services.run_roads_stage(env_overrides=env, progress=on_progress)
                services.run_builds_stage(env_overrides=env, progress=on_progress)
            except Exception as exc:  # boundary: report any extraction failure to the user
                signals.failed.emit("Extract failed", str(exc).strip() or "Extract failed", "Extract failed")
            else:
                signals.success.emit(run_state)
            finally:
                signals.finished.emit()

        threading.Thread(target=worker, daemon=True).start()

    def _handle_extract_success(self, run_state):
        self.road_viewer.load_image(self.road_viewer.image_path)
        self.build_viewer.load_image(self.build_viewer.image_path)
        self._finish_extract_timing()
        self._finish_progress()
        self.set_status("Extraction complete")
        if hasattr(self.owner, "mark_extraction_complete"):
            self.owner.mark_extraction_complete(run_state)
