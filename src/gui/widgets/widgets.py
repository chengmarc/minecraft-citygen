"""Custom input widgets used by the algorithm and extraction tabs."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

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

        row.addWidget(QtWidgets.QLabel("Seed"))
        self.seed_edit = QtWidgets.QLineEdit(str(state.get("seed", DEFAULT_SEED)), self)
        self.seed_edit.setFixedWidth(120)
        row.addWidget(self.seed_edit)

        row.addSpacing(8)
        row.addWidget(QtWidgets.QLabel("City Size"))
        city_size = QtWidgets.QComboBox(self)
        city_size.addItems(list(common.CANVAS_SIZE_OPTIONS))
        city_size.setCurrentText(algo_state["FINE"])
        row.addWidget(city_size)
        self.widgets["FINE"] = city_size

        row.addSpacing(8)
        row.addWidget(QtWidgets.QLabel("Grid Density"))
        density = QtWidgets.QComboBox(self)
        density.addItems(list(common.CLEARANCE_OPTIONS))
        density.setCurrentText(algo_state["GAP_MIXED"])
        row.addWidget(density)
        self.widgets["GAP_MIXED"] = density
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

        groups_row = QtWidgets.QHBoxLayout()
        layout.addLayout(groups_row)
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

    def _build_widget(self, name, value, parent):
        if name == "BANNED_BUILDINGS":
            widget = QtWidgets.QLineEdit(str(value), parent)
            return widget
        if name in {"FINE", "GAP_MIXED"}:
            raise RuntimeError(f"{name} is handled by the header row.")
        minimum, maximum = common.PREVIEW_SLIDER_RANGES.get(name, (-99999, 99999))
        widget = IntegerSliderControl(minimum, maximum, int(value), parent)
        return widget

    def connect_change_handler(self, handler):
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
            "seed": self.seed_edit.text().strip(),
            "algo": self.algo_values(),
        }

    def set_state(self, state):
        """Apply state to all widgets without emitting change signals."""
        algo = common.create_config_values(state.get("algo"))
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
    def __init__(self, title, area_kind, region, parent=None):
        super().__init__(title, parent)
        self.area_kind = area_kind
        start, end = common.region_to_xyz_pair(region)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(QtWidgets.QLabel("From", self))
        self.start_edit = QtWidgets.QLineEdit(f"({common.format_xyz(start)})", self)
        self.start_edit.setReadOnly(True)
        layout.addWidget(self.start_edit, 1)
        layout.addWidget(QtWidgets.QLabel("To", self))
        self.end_edit = QtWidgets.QLineEdit(f"({common.format_xyz(end)})", self)
        self.end_edit.setReadOnly(True)
        layout.addWidget(self.end_edit, 1)
        self.pick_button = QtWidgets.QPushButton("Pick", self)
        style_button(self.pick_button)
        layout.addWidget(self.pick_button)

    def connect_change_handler(self, handler):
        return None

    def set_pick_command(self, command):
        self.pick_button.clicked.connect(command)

    def get_xyz_pair(self, label_prefix):
        start = common.parse_xyz(self.start_edit.text(), f"{label_prefix} cube start")
        end = common.parse_xyz(self.end_edit.text(), f"{label_prefix} cube end")
        return start, end

    def set_xyz_pair(self, start, end):
        self.start_edit.setText(f"({common.format_xyz(start)})")
        self.end_edit.setText(f"({common.format_xyz(end)})")
