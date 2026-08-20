"""PySide6 host shell for CityGen."""

from __future__ import annotations

import os
import threading
import traceback

from config.config_algo import DEFAULT_SEED
from config.config_path import CITY_PROD
from config.config_world import SAVE
from engine.render_topdown import render_topdown_preview
from pipeline import services

from gui import common
from gui.qt_viewer import ensure_application, viewer_types

QtCore, QtGui, QtWidgets, QtImageViewer = viewer_types()
CHUNK_SIZE = 16
PROGRESS_BAR_SCALE = 1000
BUILD_SCAN_HEADROOM = 0.96

APP_STYLESHEET = """
QMainWindow, QWidget {
    background: #f4f5f8;
    color: #17202b;
}
QLabel {
    background: transparent;
}
QTabWidget::pane {
    border: 1px solid #d9dfeb;
    border-radius: 0;
    background: #fbfcfe;
}
QTabBar::tab {
    background: #e8edf7;
    color: #2a3340;
    padding: 10px 18px;
    margin-right: 6px;
    border-top-left-radius: 0;
    border-top-right-radius: 0;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #0d6efd;
}
QGroupBox {
    border: 1px solid #d9dfeb;
    border-radius: 0;
    margin-top: 12px;
    font-weight: 600;
    background: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
}
QLineEdit, QComboBox, QSpinBox {
    border: 1px solid #cfd7e6;
    border-radius: 0;
    padding: 6px 8px;
    background: #ffffff;
}
QLineEdit[readOnly="true"] {
    background: #e7ebf0;
    color: #556170;
}
QPushButton {
    border: 0;
    border-radius: 0;
    padding: 9px 14px;
    background: #dde6f8;
    color: #1e2b39;
    font-weight: 600;
}
QPushButton:hover {
    background: #d4def4;
}
QPushButton#primaryButton {
    background: #0d6efd;
    color: white;
}
QPushButton#primaryButton:hover {
    background: #0a5fd7;
}
QProgressBar {
    border: 1px solid #d3dbeb;
    border-radius: 0;
    background: #eef2f8;
    height: 12px;
    text-align: center;
}
QProgressBar::chunk {
    border-radius: 0;
    background: #0d6efd;
}
QLabel#statusLabel {
    color: #4d5a69;
}
QFrame#qtImageViewer {
    border: 1px solid #d9dfeb;
    border-radius: 0;
    background: #e3e8f0;
}
QWidget#viewerShell {
    background: #e3e8f0;
}
QLabel#viewerTitle {
    font-size: 14px;
    font-weight: 700;
}
QLabel#viewerPlaceholder {
    color: #4d5a69;
    padding: 16px;
}
"""


def style_button(button) -> None:
    shadow = QtWidgets.QGraphicsDropShadowEffect(button)
    shadow.setBlurRadius(18)
    shadow.setOffset(0, 4)
    shadow.setColor(QtGui.QColor(23, 32, 43, 80))
    button.setGraphicsEffect(shadow)


def apply_button_icon(button, icon_name: str) -> None:
    icon_path = os.path.join(common.ICON_DIR, icon_name)
    if not os.path.exists(icon_path):
        return
    if not button.text().startswith(" "):
        button.setText(f" {button.text()}")
    pixmap = QtGui.QPixmap(icon_path)
    button.setIcon(QtGui.QIcon(pixmap))
    if not pixmap.isNull():
        button.setIconSize(pixmap.size())
    font = button.font()
    if font.pointSizeF() > 0:
        font.setPointSizeF(font.pointSizeF() * 1.5)
    elif font.pointSize() > 0:
        font.setPointSize(max(1, int(round(font.pointSize() * 1.5))))
    font.setBold(True)
    button.setFont(font)


def available_qt_styles() -> list[str]:
    return list(QtWidgets.QStyleFactory.keys())


def configure_app_style(app, *, style_name: str | None = None, use_custom_theme: bool = False) -> None:
    available = {name.casefold(): name for name in available_qt_styles()}
    requested_style = style_name or "Fusion"
    resolved = available.get(requested_style.casefold())
    if resolved is None:
        options = ", ".join(sorted(available.values()))
        raise ValueError(f"Unknown Qt style {requested_style!r}. Available styles: {options}")
    app.setStyle(resolved)

    if not use_custom_theme:
        app.setStyleSheet("")
        app.setPalette(app.style().standardPalette())
        return

    app.setStyleSheet(APP_STYLESHEET)
    families = set(QtGui.QFontDatabase().families())
    for family in ("SF Pro Text", "Segoe UI Variable", "Segoe UI", "Inter", "Arial"):
        if family in families:
            app.setFont(QtGui.QFont(family, 10))
            break


class WorkerSignals(QtCore.QObject):
    status = QtCore.Signal(str)
    begin_progress = QtCore.Signal(float, float, str)
    set_progress = QtCore.Signal(float)
    pipeline_progress = QtCore.Signal(str, float, float, str)
    success = QtCore.Signal(object)
    failed = QtCore.Signal(str, str, str)
    finished = QtCore.Signal()


class RegionPreviewSignals(QtCore.QObject):
    loaded = QtCore.Signal(object, object)
    failed = QtCore.Signal(str)


class ProgressMixin:
    def _init_progress_mixin(self):
        self._progress_timer = QtCore.QTimer(self)
        self._progress_timer.timeout.connect(self._progress_tick)
        self._progress_soft_target = 0.0

    def set_status(self, status):
        self.status_label.setText(status)

    def _start_progress(self):
        self._cancel_progress_animation()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._progress_soft_target = 0.0

    def _finish_progress(self):
        self._cancel_progress_animation()
        maximum = self.progress_bar.maximum() or 100
        self.progress_bar.setValue(maximum)

    def _stop_progress(self):
        self._cancel_progress_animation()

    def _begin_script_progress(self, start_value, end_value, status):
        self._cancel_progress_animation()
        self.progress_bar.setValue(int(start_value))
        segment = max(float(end_value) - float(start_value), 0.0)
        self._progress_soft_target = float(start_value) + segment * common.SCRIPT_PROGRESS_HEADROOM
        self.set_status(status)
        self._progress_timer.start(common.SCRIPT_PROGRESS_TICK_MS)

    def _complete_script_progress(self, value):
        self._cancel_progress_animation()
        self.progress_bar.setValue(int(round(value)))

    def _progress_tick(self):
        current = float(self.progress_bar.value())
        if current >= self._progress_soft_target:
            self._cancel_progress_animation()
            return
        remaining = self._progress_soft_target - current
        step = max(0.2, remaining * 0.07)
        self.progress_bar.setValue(int(round(min(current + step, self._progress_soft_target))))

    def _cancel_progress_animation(self):
        if self._progress_timer.isActive():
            self._progress_timer.stop()


class WeightedTaskMixin(ProgressMixin):
    def _run_weighted_tasks(self, *, button, tasks, start_status, fail_title, fail_status, complete_status, on_success, success_payload):
        self._start_progress()
        button.setEnabled(False)
        signals = WorkerSignals(self)
        signals.status.connect(self.set_status)
        signals.begin_progress.connect(self._begin_script_progress)
        signals.set_progress.connect(self._complete_script_progress)
        signals.success.connect(lambda payload: (on_success(payload), self._finish_progress(), self.set_status(complete_status)))
        signals.failed.connect(self._show_failure)
        signals.finished.connect(lambda: (self._stop_progress(), button.setEnabled(True)))

        def worker():
            try:
                completed_weight = 0.0
                total_tasks = len(tasks)
                signals.status.emit(start_status)
                for index, (label, weight, func) in enumerate(tasks, start=1):
                    signals.begin_progress.emit(
                        completed_weight,
                        completed_weight + weight,
                        f"Running {index}/{total_tasks}: {label}",
                    )
                    func()
                    completed_weight += weight
                    signals.set_progress.emit(completed_weight)
            except Exception as exc:  # boundary: surface any background failure to the UI
                signals.failed.emit(fail_title, str(exc).strip() or fail_status, fail_status)
            else:
                signals.success.emit(success_payload)
            finally:
                signals.finished.emit()

        threading.Thread(target=worker, daemon=True).start()

    def _show_failure(self, title, message, status):
        self.set_status(status)
        QtWidgets.QMessageBox.critical(self, title, message)


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
        uniform_name,
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


class RegionSelectorDialog(QtWidgets.QDialog):
    def __init__(self, parent, *, title, save_path, start_xyz, end_xyz, on_apply):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(980, 720)

        self.save_path = save_path
        self.start_xyz = start_xyz
        self.end_xyz = end_xyz
        self.on_apply = on_apply
        self.preview_meta = None
        self.selection_start = None
        self.selection_world = None
        self._drag_mode = None
        self._selection_item = None
        self._view_drag_mode = None

        layout = QtWidgets.QVBoxLayout(self)
        self.viewer = QtImageViewer(initial_message="Loading world preview...", parent=self)
        self.viewer.view.viewport().installEventFilter(self)
        layout.addWidget(self.viewer, 1)

        self.status_label = QtWidgets.QLabel("Loading world preview...", self)
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)

        actions = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Cancel, parent=self)
        self.apply_button = actions.addButton("Use Selection", QtWidgets.QDialogButtonBox.AcceptRole)
        style_button(self.apply_button)
        cancel_button = actions.button(QtWidgets.QDialogButtonBox.Cancel)
        if cancel_button is not None:
            style_button(cancel_button)
        self.apply_button.setEnabled(False)
        actions.rejected.connect(self.reject)
        self.apply_button.clicked.connect(self._apply)
        layout.addWidget(actions)

        self._start_loading()

    def _start_loading(self):
        signals = RegionPreviewSignals(self)
        signals.loaded.connect(self._show_preview)
        signals.failed.connect(self._show_error)
        self._loader_signals = signals

        def worker():
            try:
                image, meta = render_topdown_preview(
                    self.save_path,
                    min(self.start_xyz[1], self.end_xyz[1]),
                    max(self.start_xyz[1], self.end_xyz[1]),
                )
            except Exception as exc:  # boundary: surface any preview-load failure in the dialog
                signals.failed.emit(str(exc).strip() or "Failed to load world preview.")
                return
            signals.loaded.emit(image, meta)

        threading.Thread(target=worker, daemon=True).start()

    def _show_error(self, message):
        self.viewer.set_message(message)
        self.status_label.setText(message)

    def _show_preview(self, image, meta):
        rgba = image.convert("RGBA")
        qimage = QtGui.QImage(rgba.tobytes("raw", "RGBA"), rgba.width, rgba.height, QtGui.QImage.Format_RGBA8888).copy()
        self.preview_meta = meta
        self.viewer.set_image(qimage)
        self._set_selection_from_world(self.start_xyz, self.end_xyz)
        self.status_label.setText("Hold Shift and drag to snap-select chunks.")

    def eventFilter(self, watched, event):
        if watched is not self.viewer.view.viewport() or self.preview_meta is None or not self.viewer.has_image():
            return super().eventFilter(watched, event)

        if event.type() == QtCore.QEvent.MouseButtonPress:
            return self._on_mouse_press(event)
        if event.type() == QtCore.QEvent.MouseMove:
            return self._on_mouse_move(event)
        if event.type() == QtCore.QEvent.MouseButtonRelease:
            return self._on_mouse_release(event)
        return super().eventFilter(watched, event)

    def _scene_point(self, position):
        view_pos = position.toPoint() if hasattr(position, "toPoint") else position
        return self.viewer.view.mapToScene(view_pos)

    def _clamp_image_point(self, position):
        if not self.viewer.has_image():
            return None
        scene_point = self._scene_point(position)
        rect = self.viewer._pixmap_item.boundingRect()
        if rect.isNull():
            return None
        ix = min(max(scene_point.x(), 0.0), rect.width() - 1)
        iy = min(max(scene_point.y(), 0.0), rect.height() - 1)
        return ix, iy

    def _image_point_to_world(self, point):
        if point is None or self.preview_meta is None:
            return None
        ix, iy = point
        span_x = self.preview_meta["x1"] - self.preview_meta["x0"] + 1
        span_z = self.preview_meta["z1"] - self.preview_meta["z0"] + 1
        world_x = self.preview_meta["x0"] + min(int(ix * self.preview_meta["step"]), span_x - 1)
        world_z = self.preview_meta["z0"] + min(int(iy * self.preview_meta["step"]), span_z - 1)
        return world_x, world_z

    def _chunk_at_position(self, position):
        world_point = self._image_point_to_world(self._clamp_image_point(position))
        if world_point is None:
            return None
        world_x, world_z = world_point
        return world_x // CHUNK_SIZE, world_z // CHUNK_SIZE

    def _set_pan_mode(self, enabled):
        desired = QtWidgets.QGraphicsView.ScrollHandDrag if enabled else QtWidgets.QGraphicsView.NoDrag
        if self.viewer.view.dragMode() != desired:
            self.viewer.view.setDragMode(desired)

    def _on_mouse_press(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            return False
        if event.modifiers() & QtCore.Qt.ShiftModifier:
            chunk = self._chunk_at_position(event.position())
            if chunk is None:
                return True
            self._drag_mode = "select"
            self.selection_start = chunk
            self._set_pan_mode(False)
            self._update_selection(chunk, chunk)
            return True
        self._drag_mode = "pan"
        self._set_pan_mode(True)
        self._view_drag_mode = self.viewer.view.dragMode()
        return False

    def _on_mouse_move(self, event):
        if self._drag_mode != "select" or self.selection_start is None:
            return False
        chunk = self._chunk_at_position(event.position())
        if chunk is None:
            return True
        self._update_selection(self.selection_start, chunk)
        return True

    def _on_mouse_release(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            return False
        if self._drag_mode == "select" and self.selection_start is not None:
            chunk = self._chunk_at_position(event.position())
            if chunk is not None:
                self._update_selection(self.selection_start, chunk)
            self._set_pan_mode(True)
            self.selection_start = None
            self._drag_mode = None
            return True
        self._drag_mode = None
        self.selection_start = None
        self._set_pan_mode(True)
        return False

    def _update_selection(self, first, second):
        if self.preview_meta is None:
            return
        chunk_x0, chunk_x1 = sorted((int(first[0]), int(second[0])))
        chunk_z0, chunk_z1 = sorted((int(first[1]), int(second[1])))
        world_x0 = max(self.preview_meta["x0"], chunk_x0 * CHUNK_SIZE)
        world_x1 = min(self.preview_meta["x1"], (chunk_x1 + 1) * CHUNK_SIZE - 1)
        world_z0 = max(self.preview_meta["z0"], chunk_z0 * CHUNK_SIZE)
        world_z1 = min(self.preview_meta["z1"], (chunk_z1 + 1) * CHUNK_SIZE - 1)
        self.selection_world = (
            (world_x0, self.start_xyz[1], world_z0),
            (world_x1, self.end_xyz[1], world_z1),
        )
        self._redraw_selection()
        self.apply_button.setEnabled(True)
        self.status_label.setText(
            f"Selection: x {world_x0} to {world_x1}, z {world_z0} to {world_z1} "
            f"({chunk_x1 - chunk_x0 + 1} x {chunk_z1 - chunk_z0 + 1} chunks)"
        )

    def _set_selection_from_world(self, start_xyz, end_xyz):
        if self.preview_meta is None or not self.viewer.has_image():
            return
        chunk_x0 = min(start_xyz[0], end_xyz[0]) // CHUNK_SIZE
        chunk_x1 = max(start_xyz[0], end_xyz[0]) // CHUNK_SIZE
        chunk_z0 = min(start_xyz[2], end_xyz[2]) // CHUNK_SIZE
        chunk_z1 = max(start_xyz[2], end_xyz[2]) // CHUNK_SIZE
        self._update_selection((chunk_x0, chunk_z0), (chunk_x1, chunk_z1))

    def _redraw_selection(self):
        if self._selection_item is not None:
            self.viewer._scene.removeItem(self._selection_item)
            self._selection_item = None
        if self.selection_world is None or self.preview_meta is None or not self.viewer.has_image():
            return
        step = self.preview_meta["step"]
        start, end = self.selection_world
        world_x0 = max(self.preview_meta["x0"], min(start[0], end[0]))
        world_x1 = min(self.preview_meta["x1"], max(start[0], end[0]))
        world_z0 = max(self.preview_meta["z0"], min(start[2], end[2]))
        world_z1 = min(self.preview_meta["z1"], max(start[2], end[2]))
        rect = QtCore.QRectF(
            (world_x0 - self.preview_meta["x0"]) / step,
            (world_z0 - self.preview_meta["z0"]) / step,
            (world_x1 + 1 - world_x0) / step,
            (world_z1 + 1 - world_z0) / step,
        )
        brush = QtGui.QBrush(QtGui.QColor(13, 110, 253, 90))
        pen = QtGui.QPen(QtGui.QColor(13, 110, 253))
        pen.setWidthF(2.0)
        self._selection_item = self.viewer._scene.addRect(rect, pen, brush)
        self._selection_item.setZValue(10)

    def _apply(self):
        if self.selection_world is None:
            return
        self.on_apply(*self.selection_world)
        self.accept()


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
            "preview_config",
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
        except ValueError as exc:
            title = "Invalid seed" if str(exc) == "Seed must be an integer." else "Invalid preview config"
            QtWidgets.QMessageBox.critical(self, title, str(exc))
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
            "city_config",
            action_icon_name="render.png",
            extra_actions=[("Output", self._open_output_folder, "folder.png")],
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
        except ValueError as exc:
            title = "Invalid seed" if str(exc) == "Seed must be an integer." else "Invalid city config"
            QtWidgets.QMessageBox.critical(self, title, str(exc))
            return

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
        self.world_edit.setFixedWidth(420)
        header.addWidget(self.world_edit)
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

    def _save_state(self):
        try:
            state = self._current_config_state()
        except ValueError:
            return
        self.owner.set_saved_config_section("extraction", state)

    def _current_config_state(self):
        road_start, road_end = self.road_group.get_xyz_pair("Road")
        house_start, house_end = self.house_group.get_xyz_pair("House")
        landmark_start, landmark_end = self.landmark_group.get_xyz_pair("Landmark")
        return {
            "world_path": self.world_edit.text().strip(),
            "road": {"start": list(road_start), "end": list(road_end)},
            "house": {"start": list(house_start), "end": list(house_end)},
            "landmark": {"start": list(landmark_start), "end": list(landmark_end)},
        }

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

    def _on_pipeline_progress(self, stage, completed, total, label):
        if self._current_stage != (stage, total):
            self._current_stage = (stage, total)
            self._start_determinate(total)
        if total == 1 and completed == 0:
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

    def _show_failure(self, title, message, status):
        self.set_status(status)
        QtWidgets.QMessageBox.critical(self, title, message)


class CityGeneratorQtApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CityGen")
        self.resize(common.APP_WIDTH, common.APP_HEIGHT)
        self.setMinimumSize(960, 720)
        if os.path.exists(common.APP_ICON_PATH):
            self.setWindowIcon(QtGui.QIcon(common.APP_ICON_PATH))

        self._saved_gui_config = common.load_saved_gui_config()

        notebook = QtWidgets.QTabWidget(self)
        notebook.addTab(ExtractionTab(self), "Extraction")
        notebook.addTab(PreviewTab(self), "Preview")
        notebook.addTab(RenderTab(self), "Render")
        self.setCentralWidget(notebook)

    def get_saved_config_section(self, section):
        value = self._saved_gui_config.get(section)
        return value if isinstance(value, dict) else None

    def set_saved_config_section(self, section, value):
        self._saved_gui_config[section] = value
        common.save_saved_gui_config(self._saved_gui_config)


def main(argv: list[str] | None = None) -> int:
    args = list(argv or [])
    style_name = None
    use_custom_theme = True
    filtered_args = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--qt-style":
            if index + 1 >= len(args):
                raise ValueError("--qt-style requires a style name.")
            style_name = args[index + 1]
            index += 2
            continue
        if arg == "--custom-qt-theme":
            use_custom_theme = True
            index += 1
            continue
        filtered_args.append(arg)
        index += 1

    _qt_core, _qt_gui, _qt_widgets, app, _owns_app = ensure_application(filtered_args)
    configure_app_style(app, style_name=style_name, use_custom_theme=use_custom_theme)
    try:
        window = CityGeneratorQtApp()
        window.show()
        return app.exec()
    except Exception:  # top-level crash boundary: mirror the Tk launcher behavior
        message = traceback.format_exc()
        try:
            with open(common.STARTUP_ERROR_LOG, "w", encoding="utf-8") as fh:
                fh.write(message)
        except OSError:
            pass
        QtWidgets.QMessageBox.critical(
            None,
            "CityGen",
            f"GUI startup failed.\n\nDetails were written to:\n{common.STARTUP_ERROR_LOG}",
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
