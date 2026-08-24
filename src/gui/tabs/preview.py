"""Preview tab: fast road-grid and city-layout PNG generation."""

from __future__ import annotations

from PySide6 import QtWidgets

from pipeline import services

from gui.core import common
from gui.core.workers import WeightedTaskMixin
from gui.widgets.qt_viewer import QtImageViewer
from gui.widgets.widgets import AlgoControlsWidget


class PreviewTab(QtWidgets.QWidget, WeightedTaskMixin):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self._peer = None
        self._init_progress_mixin()
        state = (
            owner.get_saved_config_section("algo")
            or owner.get_saved_config_section("preview")
            or common.default_algo_tab_config()
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(0)
        viewer_shell = QtWidgets.QWidget(self)
        viewer_row = QtWidgets.QHBoxLayout(viewer_shell)
        viewer_row.setContentsMargins(0, 0, 0, 0)
        viewer_row.setSpacing(12)
        self.grid_viewer = QtImageViewer(
            "Road Layout Preview",
            "Use Preview Layout to see the road network before building the final city.",
            viewer_shell,
        )
        self.city_viewer = QtImageViewer(
            "City Layout Preview",
            "Use Preview Layout to see how buildings fit into the generated road network.",
            viewer_shell,
        )
        viewer_row.addWidget(self.grid_viewer, 1)
        viewer_row.addWidget(self.city_viewer, 1)
        layout.addWidget(viewer_shell, 1)
        layout.addSpacing(20)

        self.controls = AlgoControlsWidget(
            "Preview Layout",
            self._run_preview,
            state,
            action_icon_name="preview.png",
            parent=self,
        )
        self.controls.connect_change_handler(self._save_state)
        layout.addWidget(self.controls)

        layout.addSpacing(8)
        self.status_label = QtWidgets.QLabel("", self)
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        self.refresh_prerequisite_state()

    def set_peer(self, peer):
        self._peer = peer

    def current_run_state(self):
        return self.controls.current_state()

    def refresh_prerequisite_state(self):
        ready = True
        if hasattr(self.owner, "preview_prerequisite_met"):
            ready = bool(self.owner.preview_prerequisite_met())
        self.controls.action_button.setEnabled(ready)
        self.controls.action_button.setToolTip(
            "Complete Extract Assets first." if not ready else "Generate a fast road and city layout preview."
        )

    def _save_state(self):
        state = self.controls.current_state()
        self.owner.set_saved_config_section("algo", state)
        if self._peer is not None:
            self._peer.controls.set_state(state)
        if hasattr(self.owner, "note_preview_inputs_changed"):
            self.owner.note_preview_inputs_changed()

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
        run_state = self.current_run_state()
        tasks = [
            (
                services.ROADS_SIMULATION,
                "Preparing road pieces",
                common.PREVIEW_PROGRESS_WEIGHTS[0][1],
                lambda: services.run_roads_simulation_stage(env_overrides=env),
            ),
            (
                services.BUILDS_SIMULATION,
                "Preparing building pieces",
                common.PREVIEW_PROGRESS_WEIGHTS[1][1],
                lambda: services.run_builds_simulation_stage(env_overrides=env),
            ),
            (
                services.GRID_SIMULATION,
                "Generating avenue layout",
                common.PREVIEW_PROGRESS_WEIGHTS[2][1],
                lambda: services.run_grid_simulation_stage(seed, fine, env_overrides=env),
            ),
            (
                services.CITY_SIMULATION,
                "Placing buildings",
                common.PREVIEW_PROGRESS_WEIGHTS[3][1],
                lambda: services.run_city_simulation_stage(seed, fine, env_overrides=env),
            ),
        ]
        self._run_weighted_tasks(
            button=self.controls.action_button,
            tasks=tasks,
            start_status="Preparing preview",
            fail_title="Preview failed",
            fail_status="Preview failed",
            complete_status="Preview ready",
            on_success=self._load_previews,
            success_payload=(seed, run_state),
            status_formatter=lambda _index, _total, _module, annotation: annotation,
            restore_button=self.refresh_prerequisite_state,
        )

    def _load_previews(self, payload):
        seed, run_state = payload
        self.grid_viewer.load_image(common.grid_preview_path(seed))
        self.city_viewer.load_image(common.city_preview_path(seed))
        if hasattr(self.owner, "mark_preview_complete"):
            self.owner.mark_preview_complete(run_state)
