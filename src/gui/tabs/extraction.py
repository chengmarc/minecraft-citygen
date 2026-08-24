"""Extraction tab: source-world regions and asset extraction."""

from __future__ import annotations

import threading

from PySide6 import QtCore, QtWidgets

from config.path import has_region_files
from config.world import SAVE
from pipeline import services

from gui.core import common
from gui.core.theme import apply_button_icon, style_button
from gui.core.workers import ProgressMixin, WorkerSignals
from gui.tabs._progress import EXTRACT_STAGE_STEPS, EXTRACT_TOTAL_STEPS, PROGRESS_BAR_SCALE
from gui.widgets.qt_viewer import QtImageViewer
from gui.widgets.region_dialog import RegionSelectorDialog
from gui.widgets.widgets import ExtractionAreaGroup


class ExtractionTab(QtWidgets.QWidget, ProgressMixin):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self._init_progress_mixin()
        self._extract_phase = None
        self._phase_base = 0.0
        self._phase_end = 0.0
        state = owner.get_saved_config_section("extraction") or common.default_extraction_tab_config()
        common.clear_preview_cache()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(0)
        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        self.road_viewer = QtImageViewer(
            "Road Pieces Found",
            "Extract assets to scan the selected road sample area and build a road contact sheet.",
            split,
        )
        self.road_viewer.image_path = common.ROAD_CONTACT_SHEET
        self.build_viewer = QtImageViewer(
            "Building Pieces Found",
            "Extract assets to scan the selected house and landmark areas and build a building contact sheet.",
            split,
        )
        self.build_viewer.image_path = common.BUILD_CONTACT_SHEET
        split.addWidget(self.road_viewer)
        split.addWidget(self.build_viewer)
        split.setSizes([1, 1])
        layout.addWidget(split, 1)
        layout.addSpacing(20)

        shell = QtWidgets.QWidget(self)
        shell_layout = QtWidgets.QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)

        header = QtWidgets.QHBoxLayout()
        shell_layout.addLayout(header)
        header.addWidget(QtWidgets.QLabel("Minecraft World"))
        self.world_edit = QtWidgets.QLineEdit(str(state.get("world_path", SAVE)), self)
        self.world_edit.setFixedWidth(420)
        header.addWidget(self.world_edit)
        self.browse_button = QtWidgets.QPushButton("Browse...", self)
        style_button(self.browse_button)
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

        groups = QtWidgets.QHBoxLayout()
        shell_layout.addLayout(groups)
        road_region = common.BlockRegion.from_xyz_pair(
            tuple(state["road"]["start"]),
            tuple(state["road"]["end"]),
        )
        house_region = common.BuildRegion(
            1,
            common.BlockRegion.from_xyz_pair(tuple(state["house"]["start"]), tuple(state["house"]["end"])),
        )
        landmark_region = common.BuildRegion(
            2,
            common.BlockRegion.from_xyz_pair(tuple(state["landmark"]["start"]), tuple(state["landmark"]["end"])),
        )
        self.road_group = ExtractionAreaGroup(
            "Road Sample Area",
            "Choose an area that contains the road pieces you want CityGen to reuse.",
            "road",
            road_region,
            self,
        )
        self.house_group = ExtractionAreaGroup(
            "House Sample Area",
            "Choose a sample area with your standard houses or smaller buildings.",
            "house",
            house_region,
            self,
        )
        self.landmark_group = ExtractionAreaGroup(
            "Landmark Sample Area",
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
        layout.addWidget(shell)

        layout.addSpacing(8)
        self.status_label = QtWidgets.QLabel("", self)
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, PROGRESS_BAR_SCALE)
        layout.addWidget(self.progress_bar)

        self._refresh_detected_version()

    def _save_state(self):
        try:
            state = self._current_config_state()
        except ValueError:
            return
        self.owner.set_saved_config_section("extraction", state)

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

    def _rebuild_version_combo(self, min_data_version):
        current = self.version_combo.currentData()
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        for label, value in common.version_selector_items(min_data_version):
            self.version_combo.addItem(label, value)
        self._select_version(current or common.AUTO_VERSION)
        self.version_combo.blockSignals(False)

    def _current_config_state(self):
        road_start, road_end = self.road_group.get_xyz_pair("Road")
        house_start, house_end = self.house_group.get_xyz_pair("House")
        landmark_start, landmark_end = self.landmark_group.get_xyz_pair("Landmark")
        return {
            "world_path": self.world_edit.text().strip(),
            "target_version": self.version_combo.currentData() or common.AUTO_VERSION,
            "road": {"start": list(road_start), "end": list(road_end)},
            "house": {"start": list(house_start), "end": list(house_end)},
            "landmark": {"start": list(landmark_start), "end": list(landmark_end)},
        }

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
        common.clear_pipeline_artifacts()
        self.road_viewer.set_message(
            "Extract assets to scan the selected road sample area and build a road contact sheet."
        )
        self.build_viewer.set_message(
            "Extract assets to scan the selected house and landmark areas and build a building contact sheet."
        )

    def _open_region_selector(self, group, key, title):
        save_path = self.world_edit.text().strip()
        if not save_path:
            QtWidgets.QMessageBox.critical(
                self,
                "Missing world path",
                "World Location must be set before opening the region selector.",
            )
            return
        label = {"road": "Road", "house": "House", "landmark": "Landmark"}[key]
        try:
            start, end = group.get_xyz_pair(label)
        except ValueError as exc:
            QtWidgets.QMessageBox.critical(self, "Invalid extraction region", str(exc))
            return

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

    def _on_pipeline_progress(self, stage, completed, total, label):
        step = EXTRACT_STAGE_STEPS[stage]
        weights = common.EXTRACT_STAGE_WEIGHTS
        scale = float(sum(weights))
        seg_start = sum(weights[:step - 1]) / scale * PROGRESS_BAR_SCALE
        seg_end = sum(weights[:step]) / scale * PROGRESS_BAR_SCALE

        self._cancel_progress_animation()

        if self._extract_phase != (stage, total):
            self._extract_phase = (stage, total)
            self._phase_base = max(float(self.progress_bar.value()), seg_start)
            self._phase_end = self._phase_base + (seg_end - self._phase_base) * common.EXTRACT_PHASE_FILL

        frac = max(0.0, min(float(completed) / float(total or 1), 1.0))
        target = self._phase_base + (self._phase_end - self._phase_base) * frac
        milestone = max(self.progress_bar.value(), int(round(target)))
        self.progress_bar.setValue(milestone)
        ceiling = self._phase_end if frac < 1.0 else seg_end
        self._progress_soft_target = milestone + (ceiling - milestone) * common.SCRIPT_PROGRESS_HEADROOM
        self._progress_timer.start(common.SCRIPT_PROGRESS_TICK_MS)
        annotation = label or f"{int(completed)}/{int(total)}"
        self.set_status(common.format_stage_status(step, EXTRACT_TOTAL_STEPS, stage, annotation))

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

        self._save_state()
        self.extract_button.setEnabled(False)
        self.set_status("Preparing extract...")
        self.progress_bar.setRange(0, PROGRESS_BAR_SCALE)
        self.progress_bar.setValue(0)
        self._progress_soft_target = 0.0
        self._extract_phase = None

        signals = WorkerSignals(self)
        signals.pipeline_progress.connect(self._on_pipeline_progress)
        signals.failed.connect(self._show_failure)
        signals.success.connect(lambda _payload: self._handle_extract_success())
        signals.finished.connect(lambda: (self._stop_progress(), self.extract_button.setEnabled(True)))

        def worker():
            try:
                def on_progress(stage, completed, total, label):
                    signals.pipeline_progress.emit(stage, float(completed), float(total), label)

                services.run_road_extraction_pipeline(env_overrides=env, progress=on_progress)
                services.run_build_extraction_pipeline(env_overrides=env, progress=on_progress)
            except Exception as exc:  # boundary: report any extraction failure to the user
                signals.failed.emit("Extract failed", str(exc).strip() or "Extract failed", "Extract failed")
            else:
                signals.success.emit(None)
            finally:
                signals.finished.emit()

        threading.Thread(target=worker, daemon=True).start()

    def _handle_extract_success(self):
        self.road_viewer.load_image(self.road_viewer.image_path)
        self.build_viewer.load_image(self.build_viewer.image_path)
        self._finish_progress()
        self.set_status("Extract complete")
