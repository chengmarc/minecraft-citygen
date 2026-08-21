"""The three main application tabs: Extraction, Preview, and Render."""

from __future__ import annotations

import os
import threading

from PySide6 import QtCore, QtWidgets

from config.config_path import CITY_PROD
from config.config_world import SAVE
from config.path_discovery import has_region_files
from pipeline import services

from gui import common
from gui.qt_viewer import QtImageViewer
from gui.region_dialog import RegionSelectorDialog
from gui.theme import apply_button_icon, style_button
from gui.widgets import AlgoControlsWidget, ExtractionAreaGroup
from gui.workers import ProgressMixin, WeightedTaskMixin, WorkerSignals

PROGRESS_BAR_SCALE = 1000
BUILD_SCAN_HEADROOM = 0.96


class PreviewTab(QtWidgets.QWidget, WeightedTaskMixin):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self._init_progress_mixin()
        state = owner.get_saved_config_section("preview") or common.default_algo_tab_config()

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

    def _save_state(self):
        self.owner.set_saved_config_section("preview", self.controls.current_state())

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


class RenderTab(QtWidgets.QWidget, WeightedTaskMixin):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self._init_progress_mixin()
        state = owner.get_saved_config_section("render") or common.default_algo_tab_config()

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
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

    def _save_state(self):
        self.owner.set_saved_config_section("render", self.controls.current_state())

    def _target_version_env(self):
        """Stamp the final city schematic with the version chosen on the Extraction tab."""
        world_path, choice = self._target_version_choice()
        return common.target_version_env(world_path, choice)

    def _target_version_choice(self):
        extraction = self.owner.get_saved_config_section("extraction") or {}
        return str(extraction.get("world_path", SAVE)), extraction.get("target_version", common.AUTO_VERSION)

    def _confirm_target_compatibility(self):
        """Warn before building a city that will hole out on paste. True to proceed."""
        world_path, choice = self._target_version_choice()
        report = common.target_version_report(world_path, choice, common.extracted_asset_block_ids())
        if report["ok"]:
            return True
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Warning)
        box.setWindowTitle("Blocks unsupported in target version")
        box.setText(
            f"The city will be stamped {report['target_release']}, but {len(report['offending'])} "
            f"block(s) do not exist there and will drop to air (holes) on paste.\n\n"
            f"Target {report['floor_release']} or newer on the Extraction tab for a clean paste.\n\n"
            f"Build the city anyway?"
        )
        box.setDetailedText(common.format_compat_details(report))
        box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        box.setDefaultButton(QtWidgets.QMessageBox.No)
        return box.exec() == QtWidgets.QMessageBox.Yes

    def _open_output_folder(self):
        if not os.path.isdir(CITY_PROD):
            QtWidgets.QMessageBox.critical(self, "Output folder missing", CITY_PROD)
            return
        try:
            common.open_in_file_manager(CITY_PROD)
        except OSError as exc:
            QtWidgets.QMessageBox.critical(self, "Could not open output folder", str(exc))

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

        if not self._confirm_target_compatibility():
            return
        env.update(self._target_version_env())

        tasks = [
            (services.CITY_CONSTRUCT, common.RENDER_PROGRESS_WEIGHTS[0][1], lambda: services.run_city_construct_stage(seed, fine, env_overrides=env)),
            (services.CITY_RENDER, common.RENDER_PROGRESS_WEIGHTS[1][1], lambda: services.run_city_render_stage(env_overrides=env)),
        ]
        self._run_weighted_tasks(
            button=self.controls.action_button,
            tasks=tasks,
            start_status="Starting render...",
            fail_title="Render failed",
            fail_status="Render failed",
            complete_status="Render complete",
            on_success=lambda payload: self.city_viewer.load_image(common.city_render_path(payload)),
            success_payload=seed,
        )


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
        header.addWidget(self.detected_version_edit)
        header.addSpacing(12)
        header.addWidget(QtWidgets.QLabel("Target Version"))
        self.version_combo = QtWidgets.QComboBox(self)
        for label, value in common.version_selector_items():
            self.version_combo.addItem(label, value)
        self._select_version(state.get("target_version", common.AUTO_VERSION))
        self.version_combo.setToolTip(
            "Minecraft version the output schematic targets. 'Auto' matches the "
            "source world. WorldEdit can paste into this version and newer."
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

        self._asset_block_ids = common.extracted_asset_block_ids()
        self.version_warning = QtWidgets.QLabel("", self)
        self.version_warning.setObjectName("statusLabel")
        self.version_warning.setWordWrap(True)
        shell_layout.addWidget(self.version_warning)

        self.world_edit.textChanged.connect(self._save_state)
        self.world_edit.textChanged.connect(self._refresh_detected_version)
        self.world_edit.textChanged.connect(self._refresh_version_warning)
        self.version_combo.currentIndexChanged.connect(self._save_state)
        self.version_combo.currentIndexChanged.connect(self._refresh_version_warning)
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
        self._refresh_version_warning()

    def _save_state(self):
        try:
            state = self._current_config_state()
        except ValueError:
            return
        self.owner.set_saved_config_section("extraction", state)

    def _select_version(self, value):
        index = self.version_combo.findData(value)
        self.version_combo.setCurrentIndex(index if index >= 0 else 0)

    def _current_compat_report(self):
        choice = self.version_combo.currentData() or common.AUTO_VERSION
        return common.target_version_report(self.world_edit.text().strip(), choice, self._asset_block_ids)

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

    def _refresh_version_warning(self):
        """Update the inline label to show what the chosen target can't represent."""
        if not self._asset_block_ids:
            self.version_warning.setText("Extract to check version compatibility.")
            self.version_warning.setToolTip("")
            return
        report = self._current_compat_report()
        if report["ok"]:
            self.version_warning.setText(
                f"✓ Target {report['target_release']}: all blocks supported "
                f"(pastes into {report['floor_release']} and newer)."
            )
            self.version_warning.setToolTip("")
            return
        offending = report["offending"]
        preview = ", ".join(item["block"].split(":")[-1] for item in offending[:4])
        more = "" if len(offending) <= 4 else f", +{len(offending) - 4} more"
        self.version_warning.setText(
            f"⚠ Target {report['target_release']}: {len(offending)} block(s) do not exist there "
            f"and will drop to air (holes) on paste — {preview}{more}. "
            f"These assets need {report['floor_release']}+."
        )
        self.version_warning.setToolTip(common.format_compat_details(report))

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
            headroom = BUILD_SCAN_HEADROOM if (label or "").startswith("Scanning build") else common.SCRIPT_PROGRESS_HEADROOM
            self._begin_soft_progress(label or stage, headroom=headroom)
            return
        self._cancel_progress_animation()
        self._set_progress_fraction(completed)
        if label and total == 1:
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
        env.update(common.target_version_env(state["world_path"].strip(), state["target_version"]))
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
        self._asset_block_ids = common.extracted_asset_block_ids()
        self._refresh_version_warning()
        report = self._current_compat_report()
        if not report["ok"]:
            box = QtWidgets.QMessageBox(self)
            box.setIcon(QtWidgets.QMessageBox.Warning)
            box.setWindowTitle("Blocks unsupported in target version")
            box.setText(
                f"{len(report['offending'])} block(s) used by these assets do not exist in "
                f"{report['target_release']}. WorldEdit will drop them to air (leaving holes) "
                f"when pasting into that version.\n\n"
                f"For a clean paste, target {report['floor_release']} or newer."
            )
            box.setDetailedText(common.format_compat_details(report))
            box.exec()
