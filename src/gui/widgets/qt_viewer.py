"""Reusable PySide6 image viewer widgets."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets


class ImageGraphicsView(QtWidgets.QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self._zoom_level = 0.0
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.SmartViewportUpdate)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QtGui.QColor("#e3e8f0"))
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setRenderHints(
            QtGui.QPainter.SmoothPixmapTransform | QtGui.QPainter.TextAntialiasing
        )

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        next_level = self._zoom_level + (delta / 120.0)
        next_level = min(max(next_level, -12.0), 40.0)
        if next_level == self._zoom_level:
            return
        factor = 1.12 ** (next_level - self._zoom_level)
        self._zoom_level = next_level
        self.scale(factor, factor)

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and hasattr(self.parent(), "fit_image"):
            self.parent().fit_image()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class QtImageViewer(QtWidgets.QFrame):
    def __init__(self, title="", initial_message="", parent=None):
        super().__init__(parent)
        self.image_path = None
        self._pixmap_item = None
        self._overlay_item = None
        self._has_image = False
        self.setObjectName("qtImageViewer")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.title_label = None
        if title:
            self.title_label = QtWidgets.QLabel(title, self)
            self.title_label.setObjectName("viewerTitle")
            self.title_label.hide()

        self._stack = QtWidgets.QStackedLayout()
        self._placeholder = QtWidgets.QLabel(initial_message, self)
        self._placeholder.setAlignment(QtCore.Qt.AlignCenter)
        self._placeholder.setWordWrap(True)
        self._placeholder.setObjectName("viewerPlaceholder")

        self._scene = QtWidgets.QGraphicsScene(self)
        self.view = ImageGraphicsView(self._scene, self)

        shell = QtWidgets.QWidget(self)
        shell.setObjectName("viewerShell")
        shell.setLayout(self._stack)
        self._stack.addWidget(self._placeholder)
        self._stack.addWidget(self.view)
        layout.addWidget(shell, 1)

    def set_message(self, message):
        self._has_image = False
        self._scene.clear()
        self._pixmap_item = None
        self._overlay_item = None
        self._placeholder.setText(message)
        self._stack.setCurrentWidget(self._placeholder)

    def set_image(self, image, *, image_path=None):
        pixmap = QtGui.QPixmap.fromImage(image)
        self.image_path = str(image_path) if image_path else self.image_path
        self._scene.clear()
        self._overlay_item = None
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self._has_image = True
        self._stack.setCurrentWidget(self.view)
        self.fit_image()

    def load_image(self, image_path):
        if not image_path:
            self.set_message("Image path is not set.")
            return
        path = Path(image_path)
        if not path.is_file():
            self.set_message(f"Image not found:\n{path}")
            return
        reader = QtGui.QImageReader(str(path))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            self.set_message(f"Failed to load image:\n{path}\n\n{reader.errorString()}")
            return
        self.set_image(image, image_path=path)

    def has_image(self):
        return self._has_image and self._pixmap_item is not None

    def image_rect(self):
        """Bounding rect of the loaded image in scene coordinates (null if none)."""
        if self._pixmap_item is None:
            return QtCore.QRectF()
        return self._pixmap_item.boundingRect()

    def set_overlay_rect(self, rect, pen, brush):
        """Replace any existing overlay with a single rect drawn above the image."""
        self.clear_overlay()
        item = self._scene.addRect(rect, pen, brush)
        item.setZValue(10)
        self._overlay_item = item
        return item

    def clear_overlay(self):
        if self._overlay_item is not None:
            self._scene.removeItem(self._overlay_item)
            self._overlay_item = None

    def fit_image(self):
        if not self.has_image():
            return
        self.view.resetTransform()
        self.view._zoom_level = 0.0
        self.view.fitInView(self._pixmap_item, QtCore.Qt.KeepAspectRatio)


def ensure_application(argv=None):
    """Return the running QApplication, creating one if needed."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(list(argv or [sys.argv[0]]))
        app.setApplicationName("CityGen")
    return app
