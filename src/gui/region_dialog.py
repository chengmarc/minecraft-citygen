"""Interactive world-preview dialog for snapping an extraction region to chunks."""

from __future__ import annotations

import threading

from PySide6 import QtCore, QtGui, QtWidgets

from engine.render_topdown import render_topdown_preview

from gui.qt_viewer import QtImageViewer
from gui.theme import ACCENT_RGB, style_button
from gui.workers import RegionPreviewSignals

CHUNK_SIZE = 16


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
        rect = self.viewer.image_rect()
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
        self.viewer.clear_overlay()
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
        brush = QtGui.QBrush(QtGui.QColor(*ACCENT_RGB, 90))
        pen = QtGui.QPen(QtGui.QColor(*ACCENT_RGB))
        pen.setWidthF(2.0)
        self.viewer.set_overlay_rect(rect, pen, brush)

    def _apply(self):
        if self.selection_world is None:
            return
        self.on_apply(*self.selection_world)
        self.accept()
