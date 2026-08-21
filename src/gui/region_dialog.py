"""Interactive world-preview dialog for snapping an extraction region to chunks."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from config.config_path import ARTIFACTS
from config.path_discovery import resolve_region_dir
from engine.render_topdown import render_topdown_preview

from gui.qt_viewer import QtImageViewer
from gui.theme import ACCENT_RGB
from gui.workers import RegionPreviewSignals

CHUNK_SIZE = 16
_PREVIEW_CACHE_DIR = Path(ARTIFACTS) / "world_preview"


def _preview_cache_paths(save_path):
    key = hashlib.md5(str(save_path).encode()).hexdigest()[:16]
    return _PREVIEW_CACHE_DIR / f"{key}.png", _PREVIEW_CACHE_DIR / f"{key}.json"


def _preview_region_mtime(save_path):
    try:
        region_dir = resolve_region_dir(save_path)
        mtimes = [p.stat().st_mtime for p in Path(region_dir).glob("*.mca")]
        return max(mtimes) if mtimes else 0.0
    except Exception:
        return 0.0


def cached_topdown_preview(save_path, on_progress=None):
    """render_topdown_preview with a disk cache in artifacts/world_preview/.

    The cache is keyed on save_path and invalidated when any .mca file changes.
    A hit skips the full render, so repeated region-selector opens are instant.
    ``on_progress`` is only forwarded on a cache miss (actual render).
    """
    from PIL import Image

    png_path, json_path = _preview_cache_paths(save_path)
    mtime = _preview_region_mtime(save_path)

    if png_path.exists() and json_path.exists():
        try:
            with open(json_path) as f:
                cached_meta = json.load(f)
            if cached_meta.get("mtime") == mtime:
                image = Image.open(png_path).copy()
                meta = {k: v for k, v in cached_meta.items() if k != "mtime"}
                return image, meta
        except Exception:
            pass  # fall through to re-render on any cache read failure

    image, meta = render_topdown_preview(save_path, on_progress=on_progress)

    try:
        png_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(png_path)
        with open(json_path, "w") as f:
            json.dump({**meta, "mtime": mtime}, f)
    except Exception:
        pass  # cache write failure is non-fatal

    return image, meta


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

        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, 0)  # indeterminate while loading
        layout.addWidget(self.progress_bar)

        actions = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Cancel, parent=self)
        self.apply_button = actions.addButton("Use Selection", QtWidgets.QDialogButtonBox.AcceptRole)
        self.apply_button.setEnabled(False)
        actions.rejected.connect(self.reject)
        self.apply_button.clicked.connect(self._apply)
        layout.addWidget(actions)

        self._start_loading()

    def _start_loading(self):
        signals = RegionPreviewSignals(self)
        signals.loaded.connect(self._show_preview)
        signals.failed.connect(self._show_error)
        signals.progress.connect(self._on_preview_progress)
        self._loader_signals = signals

        def worker():
            try:
                image, meta = cached_topdown_preview(
                    self.save_path,
                    on_progress=lambda done, total: signals.progress.emit(done, total),
                )
            except Exception as exc:  # boundary: surface any preview-load failure in the dialog
                signals.failed.emit(str(exc).strip() or "Failed to load world preview.")
                return
            signals.loaded.emit(image, meta)

        threading.Thread(target=worker, daemon=True).start()

    def _on_preview_progress(self, completed, total):
        if self.progress_bar.maximum() == 0:  # switch from indeterminate to determinate on first tick
            self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(completed)

    def _show_error(self, message):
        self.progress_bar.setVisible(False)
        self.viewer.set_message(message)
        self.status_label.setText(message)

    def _show_preview(self, image, meta):
        self.progress_bar.setVisible(False)
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
