"""The three main application tabs: Extraction, Preview, and Render."""

from __future__ import annotations

import os
import threading

from PySide6 import QtCore, QtWidgets

from config.path import CITY_PROD
from config.world import SAVE
from config.path import has_region_files
from pipeline import services

from gui.core import common
from gui.widgets.qt_viewer import QtImageViewer
from gui.widgets.region_dialog import RegionSelectorDialog
from gui.core.theme import apply_button_icon, style_button
from gui.widgets.widgets import AlgoControlsWidget, ExtractionAreaGroup
from gui.core.workers import ProgressMixin, WeightedTaskMixin, WorkerSignals

PROGRESS_BAR_SCALE = 1000


class PreviewTab(QtWidgets.QWidget, WeightedTaskMixin):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self._peer = None
        self._init_progress_mixin()
        state = (owner.get_saved_config_section("algo")
                 or owner.get_saved_config_section("preview")
                 or common.default_algo_tab_config())

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(0)
        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        self.grid_viewer = QtImageViewer("Grid Preview", "Click Preview to generate the grid preview image.", split)
        self.city_viewer = QtImageViewer("City Preview", "Click Preview to generate the city preview image.", split)
        split.addWidget(self.grid_viewer)
        split.addWidget(self.city_viewer)
        split.setSizes([1, 1])
        layout.addWidget(split, 1)
        layout.addSpacing(20)

        self.controls = AlgoControlsWidget(
            "Preview",
            self._run_preview,
            state,
            action_icon_name="preview.png",
            parent=self,
        )
        self.controls.connect_change_handler(self._save_state)
        layout.addWidget(self.controls)

        self.status_label = QtWidgets.QLabel("", self)
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

    def set_peer(self, peer):
        self._peer = peer

    def _save_state(self):
        state = self.controls.current_state()
        self.owner.set_saved_config_section("algo", state)
        if self._peer is not None:
            self._peer.controls.set_state(state)

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

        tasks = [
            (services.ROADS_SIMULATION, common.PREVIEW_PROGRESS_WEIGHTS[0][1], lambda: services.run_roads_simulation_stage(env_overrides=env)),
            (services.BUILDS_SIMULATION, common.PREVIEW_PROGRESS_WEIGHTS[1][1], lambda: services.run_builds_simulation_stage(env_overrides=env)),
            (services.GRID_SIMULATION, common.PREVIEW_PROGRESS_WEIGHTS[2][1], lambda: services.run_grid_simulation_stage(seed, fine, env_overrides=env)),
            (services.CITY_SIMULATION, common.PREVIEW_PROGRESS_WEIGHTS[3][1], lambda: services.run_city_simulation_stage(seed, fine, env_overrides=env)),
        ]
        self._run_weighted_tasks(
            button=self.controls.action_button,
            tasks=tasks,
            start_status="Starting preview...",
            fail_title="Preview failed",
            fail_status="Preview failed",
            complete_status="Preview complete",
            on_success=self._load_previews,
            success_payload=seed,
        )

    def _load_previews(self, seed):
        self.grid_viewer.load_image(common.grid_preview_path(seed))
        self.city_viewer.load_image(common.city_preview_path(seed))


class RenderTab(QtWidgets.QWidget, ProgressMixin):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self._peer = None
        self._init_progress_mixin()
        state = (owner.get_saved_config_section("algo")
                 or owner.get_saved_config_section("render")
                 or common.default_algo_tab_config())

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(0)
        self.city_viewer = QtImageViewer("City Schematic Render", "Click Render to construct and render the city schematic.", self)
        layout.addWidget(self.city_viewer, 1)
        layout.addSpacing(20)

        self.controls = AlgoControlsWidget(
            "Render",
            self._run_render,
            state,
            action_icon_name="render.png",
            extra_actions=[("Output Folder", self._open_output_folder, "folder.png")],
            parent=self,
        )
        self.controls.connect_change_handler(self._save_state)
        layout.addWidget(self.controls)

        self.status_label = QtWidgets.QLabel("", self)
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, PROGRESS_BAR_SCALE)
        layout.addWidget(self.progress_bar)

    def set_peer(self, peer):
        self._peer = peer

    def _save_state(self):
        state = self.controls.current_state()
        self.owner.set_saved_config_section("algo", state)
        if self._peer is not None:
            self._peer.controls.set_state(state)

    def _stamp_version_env(self):
        """Stamp the final city schematic with the source world's version.

        Forward-only: the schematic is stamped with the source version and
        WorldEdit upgrades it forward on paste.
        """
        extraction = self.owner.get_saved_config_section("extraction") or {}
        world_path = str(extraction.get("world_path", SAVE))
        return common.stamp_version_env(world_path)

    def _open_output_folder(self):
        if not os.path.isdir(CITY_PROD):
            QtWidgets.QMessageBox.critical(self, "Output folder missing", CITY_PROD)
            return
        try:
            common.open_in_file_manager(CITY_PROD)
        except OSError as exc:
            QtWidgets.QMessageBox.critical(self, "Could not open output folder", str(exc))

    def _on_pipeline_progress(self, stage, completed, total, label):
        n = int(completed)
        c_weights = common.RENDER_CONSTRUCT_WEIGHTS
        r_weight = common.RENDER_RENDER_WEIGHT
        scale = float(sum(c_weights) + r_weight)

        self._cancel_progress_animation()

        if stage == "Constructing":
            prefix = sum(c_weights[:n])
            milestone = int(round(prefix / scale * PROGRESS_BAR_SCALE))
            self.progress_bar.setValue(milestone)
            if n < len(c_weights):
                next_ms = int(round((prefix + c_weights[n]) / scale * PROGRESS_BAR_SCALE))
                self._progress_soft_target = milestone + int(
                    (next_ms - milestone) * common.SCRIPT_PROGRESS_HEADROOM
                )
                self._progress_timer.start(common.SCRIPT_PROGRESS_TICK_MS)
        else:
            c_bar = int(round(sum(c_weights) / scale * PROGRESS_BAR_SCALE))
            t = float(total) if total > 0 else 1.0
            r_span = PROGRESS_BAR_SCALE - c_bar
            milestone = c_bar + int(round(n / t * r_span))
            self.progress_bar.setValue(milestone)
            if n < total:
                next_ms = c_bar + int(round((n + 1) / t * r_span))
                self._progress_soft_target = milestone + int(
                    (next_ms - milestone) * common.SCRIPT_PROGRESS_HEADROOM
                )
                self._progress_timer.start(common.SCRIPT_PROGRESS_TICK_MS)

        self.set_status(label or f"{stage} {n}/{int(total)}")

    def _run_render(self):
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

        env.update(self._stamp_version_env())

        self.controls.action_button.setEnabled(False)
        self.set_status("Starting render...")
        self.progress_bar.setRange(0, PROGRESS_BAR_SCALE)
        self.progress_bar.setValue(0)

        signals = WorkerSignals(self)
        signals.pipeline_progress.connect(self._on_pipeline_progress)
        signals.failed.connect(self._show_failure)
        signals.success.connect(lambda payload: (
            self.city_viewer.load_image(common.city_render_path(payload)),
            self._finish_progress(),
            self.set_status("Render complete"),
        ))
        signals.finished.connect(lambda: (self._stop_progress(), self.controls.action_button.setEnabled(True)))

        def on_progress(stage, completed, total, label):
            signals.pipeline_progress.emit(stage, float(completed), float(total), label or "")

        def worker():
            try:
                services.run_city_construct_stage(seed, fine, env_overrides=env, progress=on_progress)
                services.run_city_render_stage(env_overrides=env, progress=on_progress)
            except Exception as exc:  # boundary: surface any background failure to the UI
                signals.failed.emit("Render failed", str(exc).strip() or "Render failed", "Render failed")
            else:
                signals.success.emit(seed)
            finally:
                signals.finished.emit()

        threading.Thread(target=worker, daemon=True).start()


class ExtractionTab(QtWidgets.QWidget, ProgressMixin):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self._init_progress_mixin()
        self._current_stage = (None, None)
        self._progress_stage_total = 1.0
        state = owner.get_saved_config_section("extraction") or common.default_extraction_tab_config()
        common.clear_preview_cache()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(0)
        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        self.road_viewer = QtImageViewer("Extracted Road Assets", "Click Extract to scan road assets and render the contact sheet.", split)
        self.road_viewer.image_path = common.ROAD_CONTACT_SHEET
        self.build_viewer = QtImageViewer("Extracted Build Assets", "Click Extract to scan build assets and render the contact sheet.", split)
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
        header.addWidget(QtWidgets.QLabel("World Location"))
        self.world_edit = QtWidgets.QLineEdit(str(state.get("world_path", SAVE)), self)
        self.world_edit.setFixedWidth(360)
        header.addWidget(self.world_edit)
        self.browse_button = QtWidgets.QPushButton("Browse...", self)
        self.browse_button.clicked.connect(self._browse_world)
        header.addWidget(self.browse_button)
        header.addSpacing(12)
        header.addWidget(QtWidgets.QLabel("World Version"))
        self.detected_version_edit = QtWidgets.QLineEdit(self)
        self.detected_version_edit.setReadOnly(True)
        self.detected_version_edit.setPlaceholderText("—")
        self.detected_version_edit.setToolTip(
            "The source world's Minecraft version. Outputs are stamped with it "
            "and WorldEdit upgrades them forward on paste, so they work in this "
            "version and any newer one."
        )
        header.addWidget(self.detected_version_edit)
        header.addSpacing(12)
        header.addWidget(QtWidgets.QLabel("Target Version"))
        self.version_combo = QtWidgets.QComboBox(self)
        for label, value in common.version_selector_items():
            self.version_combo.addItem(label, value)
        self._select_version(state.get("target_version", common.AUTO_VERSION))
        self.version_combo.setToolTip(
            "Indicator only: the Minecraft version you plan to paste into (the "
            "source version or newer). It does not change the output -- the "
            "schematic is always stamped with the source world's version and "
            "WorldEdit upgrades it forward on paste."
        )
        header.addWidget(self.version_combo)
        header.addStretch(1)
        self.extract_button = QtWidgets.QPushButton("Extract", self)
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
        house_region = common.BuildRegion(1, common.BlockRegion.from_xyz_pair(tuple(state["house"]["start"]), tuple(state["house"]["end"])))
        landmark_region = common.BuildRegion(2, common.BlockRegion.from_xyz_pair(tuple(state["landmark"]["start"]), tuple(state["landmark"]["end"])))
        self.road_group = ExtractionAreaGroup("Road Assets Region", "road", road_region, self)
        self.house_group = ExtractionAreaGroup("House Assets Region", "house", house_region, self)
        self.landmark_group = ExtractionAreaGroup("Landmark Assets Region", "landmark", landmark_region, self)
        self.road_group.set_pick_command(lambda: self._open_region_selector(self.road_group, "road", "Road Region Selector"))
        self.house_group.set_pick_command(lambda: self._open_region_selector(self.house_group, "house", "House Region Selector"))
        self.landmark_group.set_pick_command(lambda: self._open_region_selector(self.landmark_group, "landmark", "Landmark Region Selector"))
        for group in (self.road_group, self.house_group, self.landmark_group):
            groups.addWidget(group, 1)

        self.world_edit.textChanged.connect(self._save_state)
        self.world_edit.textChanged.connect(self._refresh_detected_version)
        self.version_combo.currentIndexChanged.connect(self._save_state)
        self.road_group.connect_change_handler(self._save_state)
        self.house_group.connect_change_handler(self._save_state)
        self.landmark_group.connect_change_handler(self._save_state)
        layout.addWidget(shell)

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
            self, "Select Minecraft World Folder", self.world_edit.text().strip() or ""
        )
        if not folder:
            return
        if not has_region_files(folder):
            QtWidgets.QMessageBox.warning(
                self, "Not a Minecraft world",
                f"No region files (.mca) were found in:\n{folder}\n\n"
                "Please select a valid Minecraft world folder.",
            )
            return
        self.world_edit.setText(folder)
        common.clear_pipeline_artifacts()
        self.road_viewer.set_message("Click Extract to scan road assets and render the contact sheet.")
        self.build_viewer.set_message("Click Extract to scan build assets and render the contact sheet.")

    def _open_region_selector(self, group, key, title):
        save_path = self.world_edit.text().strip()
        if not save_path:
            QtWidgets.QMessageBox.critical(self, "Missing world path", "World Location must be set before opening the region selector.")
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

    def _start_determinate(self, total):
        self._cancel_progress_animation()
        self._progress_stage_total = max(float(total), 1.0)
        self.progress_bar.setRange(0, PROGRESS_BAR_SCALE)
        self.progress_bar.setValue(0)

    def _set_progress_fraction(self, completed):
        fraction = max(0.0, min(float(completed) / self._progress_stage_total, 1.0))
        self.progress_bar.setValue(int(round(fraction * PROGRESS_BAR_SCALE)))

    def _begin_soft_progress(self, status, *, headroom=common.SCRIPT_PROGRESS_HEADROOM):
        self._cancel_progress_animation()
        self.progress_bar.setValue(0)
        self._progress_soft_target = PROGRESS_BAR_SCALE * float(headroom)
        self.set_status(status)
        self._progress_timer.start(common.SCRIPT_PROGRESS_TICK_MS)

    @staticmethod
    def _is_indeterminate_start(completed, total):
        # Contract with pipeline.services: a stage that cannot report granular
        # progress emits a single (completed=0, total=1) tick to ask the UI for
        # an animated "soft" progress bar instead of a determinate fraction.
        return total == 1 and completed == 0

    def _on_pipeline_progress(self, stage, completed, total, label):
        if self._current_stage != (stage, total):
            self._current_stage = (stage, total)
            self._start_determinate(total)
        if self._is_indeterminate_start(completed, total):
            self._begin_soft_progress(label or stage, headroom=common.SCRIPT_PROGRESS_HEADROOM)
            return
        self._cancel_progress_animation()
        self._set_progress_fraction(completed)
        if label:
            self.set_status(label)
        else:
            self.set_status(f"{stage} {int(completed)}/{int(total)}")

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
        self._current_stage = (None, None)
        self.extract_button.setEnabled(False)
        self.set_status("Preparing extract...")
        self._start_determinate(100)

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
