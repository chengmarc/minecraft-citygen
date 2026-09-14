"""Action/control panels shared by workflow tabs."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from config.world import SAVE

from gui.core import common
from gui.core.theme import apply_button_icon, style_button
from gui.widgets.widgets import AlgoControlsWidget, ExtractionAreaGroup


class ExtractionControlPanel(QtWidgets.QWidget):
    browse_requested = QtCore.Signal()
    extract_requested = QtCore.Signal()

    def __init__(self, state, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QtWidgets.QHBoxLayout()
        layout.addLayout(header)
        header.addWidget(QtWidgets.QLabel("Minecraft World"))
        self.world_edit = QtWidgets.QLineEdit(str(state.get("world_path", SAVE)), self)
        self.world_edit.setPlaceholderText("Select a Minecraft world folder")
        self.world_edit.setFixedWidth(420)
        header.addWidget(self.world_edit)

        self.browse_button = QtWidgets.QPushButton("Browse...", self)
        style_button(self.browse_button)
        self.browse_button.setFixedHeight(self.world_edit.sizeHint().height())
        self.browse_button.clicked.connect(lambda _checked=False: self.browse_requested.emit())
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
        self.select_version(state.get("target_version", common.AUTO_VERSION))
        self.version_combo.setToolTip(
            "Lets you confirm which Minecraft version you plan to paste into. "
            "Minecraft CityGen still stamps the exported files to the source world's version."
        )
        header.addWidget(self.version_combo)

        header.addStretch(1)
        self.extract_button = QtWidgets.QPushButton("Extract", self)
        self.extract_button.setObjectName("primaryButton")
        style_button(self.extract_button)
        apply_button_icon(self.extract_button, "extract.png")
        self.extract_button.clicked.connect(lambda _checked=False: self.extract_requested.emit())
        header.addWidget(self.extract_button)

        layout.addSpacing(10)
        groups = QtWidgets.QHBoxLayout()
        layout.addLayout(groups)

        self.road_group = ExtractionAreaGroup(
            "Road Area",
            "Choose an area that contains the road pieces you want Minecraft CityGen to reuse.",
            "road",
            self._region_from_state(state.get("road"), area_kind="road"),
            self,
        )
        self.house_group = ExtractionAreaGroup(
            "House Area",
            "Choose a sample area with your standard houses or smaller buildings.",
            "house",
            self._region_from_state(state.get("house"), area_kind="house"),
            self,
        )
        self.landmark_group = ExtractionAreaGroup(
            "Landmark Area",
            "Choose a sample area with taller or special buildings that should stand out in the city.",
            "landmark",
            self._region_from_state(state.get("landmark"), area_kind="landmark"),
            self,
        )
        for group in self.area_groups():
            groups.addWidget(group, 1)

    def area_groups(self):
        return self.road_group, self.house_group, self.landmark_group

    def connect_change_handler(self, handler):
        self.world_edit.textChanged.connect(handler)
        self.version_combo.currentIndexChanged.connect(handler)
        for group in self.area_groups():
            group.connect_change_handler(handler)

    def set_pick_commands(self, *, road, house, landmark):
        self.road_group.set_pick_command(road)
        self.house_group.set_pick_command(house)
        self.landmark_group.set_pick_command(landmark)

    def select_version(self, value):
        index = self.version_combo.findData(value)
        self.version_combo.setCurrentIndex(index if index >= 0 else 0)

    def rebuild_version_combo(self, min_data_version):
        current = self.version_combo.currentData()
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        for label, value in common.version_selector_items(min_data_version):
            self.version_combo.addItem(label, value)
        self.select_version(current or common.AUTO_VERSION)
        self.version_combo.blockSignals(False)

    def set_world_ready(self, ready):
        for group in self.area_groups():
            group.set_world_ready(ready)

    def clear_area_selections(self):
        for group in self.area_groups():
            group.clear_selection()

    def set_extract_enabled(self, enabled):
        self.extract_button.setEnabled(bool(enabled))

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


class GenerationControlPanel(AlgoControlsWidget):
    def __init__(self, state, build_callback, open_output_callback, parent=None):
        super().__init__(
            "Build",
            build_callback,
            state,
            action_icon_name="render.png",
            extra_actions=[("Copy", open_output_callback, "folder.png")],
            show_seed=False,
            parent=parent,
        )
