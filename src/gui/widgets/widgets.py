"""Custom input widgets used by the algorithm and extraction tabs."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from config.algo import DEFAULT_SEED

from gui.core import common
from gui.core.theme import apply_button_icon, style_button


class IntegerSliderControl(QtWidgets.QWidget):
    valueChanged = QtCore.Signal(int)

    def __init__(self, minimum, maximum, value, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.slider.setRange(minimum, maximum)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(1)
        self.slider.setTickInterval(1)
        self.slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.slider.setValue(int(value))
        self.slider.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self.slider, 1)

        self.value_label = QtWidgets.QLabel("", self)
        self.value_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.value_label.setMinimumWidth(28)
        layout.addWidget(self.value_label)

        self._on_value_changed(self.slider.value())

    def _on_value_changed(self, value):
        self.value_label.setText(str(value))
        self.valueChanged.emit(value)

    def value(self):
        return self.slider.value()

    def setValue(self, value):
        self.slider.setValue(int(value))


class AlgoControlsWidget(QtWidgets.QWidget):
    def __init__(
        self,
        action_text,
        action_callback,
        state,
        action_icon_name=None,
        extra_actions=None,
        parent=None,
    ):
        super().__init__(parent)
        self.widgets = {}
        algo_state = common.create_config_values(state.get("algo"))

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        row = QtWidgets.QHBoxLayout()
        layout.addLayout(row)

        self.advanced_toggle = QtWidgets.QToolButton(self)
        self.advanced_toggle.setObjectName("advancedToggle")
        self.advanced_toggle.setText("Basic Settings")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        style_button(self.advanced_toggle)
        self.advanced_toggle.toggled.connect(self._toggle_advanced)

        row.addSpacing(8)
        row.addWidget(QtWidgets.QLabel("Layout Seed"))
        self.seed_edit = QtWidgets.QLineEdit(str(state.get("seed", DEFAULT_SEED)), self)
        self.seed_edit.setFixedWidth(65)
        self.seed_edit.setValidator(QtGui.QIntValidator(-2147483647, 2147483647, self.seed_edit))
        self.seed_edit.setToolTip("Use the same seed again to regenerate the same city layout.")
        self.advanced_toggle.setFixedHeight(self.seed_edit.sizeHint().height())
        row.addWidget(self.seed_edit)

        row.addSpacing(8)
        row.addWidget(QtWidgets.QLabel("City Size"))
        city_size = QtWidgets.QComboBox(self)
        city_size.addItems(list(common.CANVAS_SIZE_OPTIONS))
        city_size.setCurrentText(algo_state["FINE"])
        row.addWidget(city_size)
        self.widgets["FINE"] = city_size

        row.addSpacing(8)
        row.addWidget(QtWidgets.QLabel("Road Density"))
        density = QtWidgets.QComboBox(self)
        density.addItems(list(common.CLEARANCE_OPTIONS))
        density.setCurrentText(algo_state["GAP_MIXED"])
        row.addWidget(density)
        self.widgets["GAP_MIXED"] = density
        row.addSpacing(8)
        row.addWidget(self.advanced_toggle)
        row.addStretch(1)

        if extra_actions:
            for text, command, icon_name in extra_actions:
                button = QtWidgets.QPushButton(text, self)
                style_button(button)
                if icon_name:
                    apply_button_icon(button, icon_name)
                button.clicked.connect(command)
                row.addWidget(button)

        self.action_button = QtWidgets.QPushButton(action_text, self)
        self.action_button.setObjectName("primaryButton")
        style_button(self.action_button)
        if action_icon_name:
            apply_button_icon(self.action_button, action_icon_name)
        self.action_button.clicked.connect(action_callback)
        row.addWidget(self.action_button)

        self.advanced_panel = QtWidgets.QWidget(self)
        self.advanced_panel.setVisible(False)
        advanced_layout = QtWidgets.QVBoxLayout(self.advanced_panel)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(10)
        groups_row = QtWidgets.QHBoxLayout()
        advanced_layout.addLayout(groups_row)
        for title, names in common.PREVIEW_CONFIG_GROUPS:
            box = QtWidgets.QGroupBox(title, self)
            form = QtWidgets.QFormLayout(box)
            form.setContentsMargins(20, 20, 20, 20)
            form.setLabelAlignment(QtCore.Qt.AlignLeft)
            form.setVerticalSpacing(18)
            for name in names:
                label, description = common.PREVIEW_CONFIG_LOOKUP[name]
                widget = self._build_widget(name, algo_state[name], box)
                widget.setToolTip(description)
                form.addRow(label, widget)
                self.widgets[name] = widget
            groups_row.addWidget(box, 1)
        layout.addSpacing(10)
        layout.addWidget(self.advanced_panel)

    def _build_widget(self, name, value, parent):
        if name == "BANNED_BUILDINGS":
            widget = QtWidgets.QLineEdit(str(value), parent)
            widget.setPlaceholderText("e.g. 001, 002")
            return widget
        if name in {"FINE", "GAP_MIXED"}:
            raise RuntimeError(f"{name} is handled by the header row.")
        minimum, maximum = common.PREVIEW_SLIDER_RANGES.get(name, (-99999, 99999))
        widget = IntegerSliderControl(minimum, maximum, int(value), parent)
        return widget

    def _toggle_advanced(self, visible):
        self.advanced_panel.setVisible(bool(visible))
        self.advanced_toggle.setText("Advanced Settings" if visible else "Basic Settings")

    def set_advanced_visible(self, visible, *, emit_change=True):
        visible = bool(visible)
        if emit_change:
            self.advanced_toggle.setChecked(visible)
            return
        self.advanced_toggle.blockSignals(True)
        self.advanced_toggle.setChecked(visible)
        self.advanced_toggle.blockSignals(False)
        self._toggle_advanced(visible)

    def connect_change_handler(self, handler):
        self.advanced_toggle.toggled.connect(handler)
        self.seed_edit.textChanged.connect(handler)
        for name, widget in self.widgets.items():
            if isinstance(widget, QtWidgets.QLineEdit):
                widget.textChanged.connect(handler)
            elif isinstance(widget, QtWidgets.QComboBox):
                widget.currentTextChanged.connect(handler)
            else:
                widget.valueChanged.connect(handler)

    def algo_values(self):
        values = common.create_config_values()
        for name, widget in self.widgets.items():
            if isinstance(widget, QtWidgets.QLineEdit):
                values[name] = widget.text().strip()
            elif isinstance(widget, QtWidgets.QComboBox):
                values[name] = widget.currentText().strip()
            else:
                values[name] = str(widget.value())
        return values

    def current_state(self):
        return {
            "advanced": self.advanced_toggle.isChecked(),
            "seed": self.seed_edit.text().strip(),
            "algo": self.algo_values(),
        }

    def set_state(self, state):
        """Apply state to all widgets without emitting change signals."""
        algo = common.create_config_values(state.get("algo"))
        self.set_advanced_visible(state.get("advanced", False), emit_change=False)
        self.seed_edit.blockSignals(True)
        self.seed_edit.setText(str(state.get("seed", DEFAULT_SEED)))
        self.seed_edit.blockSignals(False)
        for name, widget in self.widgets.items():
            widget.blockSignals(True)
            value = algo.get(name, "")
            if isinstance(widget, QtWidgets.QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QtWidgets.QComboBox):
                widget.setCurrentText(str(value))
            else:
                widget.setValue(int(value))
            widget.blockSignals(False)


class ExtractionAreaGroup(QtWidgets.QGroupBox):
    def __init__(self, title, description, area_kind, region, parent=None):
        super().__init__(title, parent)
        self.area_kind = area_kind
        self.setToolTip(description)
        self._change_handlers = []
        self._start_xyz = None
        self._end_xyz = None
        self.setObjectName("extractionAreaCard")

        frame = QtWidgets.QVBoxLayout(self)
        frame.setContentsMargins(18, 18, 18, 18)
        frame.setSpacing(12)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        frame.addLayout(header)

        self.title_label = QtWidgets.QLabel(title, self)
        self.title_label.setObjectName("cardTitle")
        self.title_label.setToolTip(description)
        header.addWidget(self.title_label)
        header.addStretch(1)

        self.status_chip = QtWidgets.QLabel(self)
        self.status_chip.setObjectName("statusChip")
        self.status_chip.setAlignment(QtCore.Qt.AlignCenter)
        header.addWidget(self.status_chip)

        self.detail_label = QtWidgets.QLabel(self)
        self.detail_label.setObjectName("cardDetail")
        self.detail_label.setWordWrap(True)
        frame.addWidget(self.detail_label)

        actions = QtWidgets.QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)
        frame.addLayout(actions)

        self.pick_button = QtWidgets.QPushButton("Choose on Map", self)
        style_button(self.pick_button)
        self.pick_button.setToolTip(description)
        self.pick_button.setFixedHeight(self.pick_button.sizeHint().height() + 4)
        self.pick_button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        actions.addWidget(self.pick_button)

        if region is None:
            self._clear_selection()
        else:
            start, end = common.region_to_xyz_pair(region)
            self.set_xyz_pair(start, end, emit_change=False)

    def connect_change_handler(self, handler):
        self._change_handlers.append(handler)

    def set_pick_command(self, command):
        self.pick_button.clicked.connect(command)

    def set_world_ready(self, ready):
        self.pick_button.setEnabled(bool(ready))

    def _clear_selection(self):
        self._start_xyz = None
        self._end_xyz = None
        self._set_status(False)

    def clear_selection(self, *, emit_change=True):
        self._clear_selection()
        if emit_change:
            for handler in self._change_handlers:
                handler()

    def _set_status(self, selected):
        self.status_chip.setProperty("selected", bool(selected))
        self.status_chip.setText("Selected" if selected else "Not Selected")
        self.status_chip.style().unpolish(self.status_chip)
        self.status_chip.style().polish(self.status_chip)
        if selected:
            start, end = self.get_xyz_pair(self.title_label.text())
            self.detail_label.setText(f"{self._chunk_span_text(start, end)} selected")
        else:
            self.detail_label.setText("No area selected")

    def _chunk_span_text(self, start, end):
        min_x, max_x = sorted((int(start[0]), int(end[0])))
        min_z, max_z = sorted((int(start[2]), int(end[2])))
        x_chunks = max_x // 16 - min_x // 16 + 1
        z_chunks = max_z // 16 - min_z // 16 + 1
        return f"{x_chunks} x {z_chunks} chunks"

    def get_xyz_pair(self, label_prefix):
        if self._start_xyz is None or self._end_xyz is None:
            raise ValueError(f"{label_prefix} area has not been selected.")
        return self._start_xyz, self._end_xyz

    def has_selection(self):
        return self._start_xyz is not None and self._end_xyz is not None

    def set_xyz_pair(self, start, end, *, emit_change=True):
        self._start_xyz = tuple(int(value) for value in start)
        self._end_xyz = tuple(int(value) for value in end)
        self._set_status(True)
        if emit_change:
            for handler in self._change_handlers:
                handler()
