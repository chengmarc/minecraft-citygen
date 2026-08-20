"""Reusable PySide6 image viewer widgets."""

from __future__ import annotations

import sys
from pathlib import Path
_VIEWER_TYPES = None


def _load_qt():
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError as exc:  # pragma: no cover - depends on optional runtime
        raise RuntimeError(
            "PySide6 is not installed. Run `python -m pip install PySide6` to use the Qt viewer."
        ) from exc
    return QtCore, QtGui, QtWidgets


def viewer_types():
    global _VIEWER_TYPES
    if _VIEWER_TYPES is not None:
        return _VIEWER_TYPES

    qt_core, qt_gui, qt_widgets = _load_qt()

    class ImageGraphicsView(qt_widgets.QGraphicsView):
        def __init__(self, scene, parent=None):
            super().__init__(scene, parent)
            self._zoom_level = 0.0
            self.setDragMode(qt_widgets.QGraphicsView.ScrollHandDrag)
            self.setTransformationAnchor(qt_widgets.QGraphicsView.AnchorUnderMouse)
            self.setResizeAnchor(qt_widgets.QGraphicsView.AnchorUnderMouse)
            self.setViewportUpdateMode(qt_widgets.QGraphicsView.SmartViewportUpdate)
            self.setHorizontalScrollBarPolicy(qt_core.Qt.ScrollBarAlwaysOff)
            self.setVerticalScrollBarPolicy(qt_core.Qt.ScrollBarAlwaysOff)
            self.setBackgroundBrush(qt_gui.QColor("#e3e8f0"))
            self.setFrameShape(qt_widgets.QFrame.NoFrame)
            self.setRenderHints(
                qt_gui.QPainter.SmoothPixmapTransform | qt_gui.QPainter.TextAntialiasing
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
            if event.button() == qt_core.Qt.LeftButton and hasattr(self.parent(), "fit_image"):
                self.parent().fit_image()
                event.accept()
                return
            super().mouseDoubleClickEvent(event)

    class QtImageViewer(qt_widgets.QFrame):
        def __init__(self, title="", initial_message="", parent=None):
            super().__init__(parent)
            self.image_path = None
            self._pixmap_item = None
            self._has_image = False
            self.setObjectName("qtImageViewer")

            layout = qt_widgets.QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)

            self.title_label = None
            if title:
                self.title_label = qt_widgets.QLabel(title, self)
                self.title_label.setObjectName("viewerTitle")
                self.title_label.hide()

            self._stack = qt_widgets.QStackedLayout()
            self._placeholder = qt_widgets.QLabel(initial_message, self)
            self._placeholder.setAlignment(qt_core.Qt.AlignCenter)
            self._placeholder.setWordWrap(True)
            self._placeholder.setObjectName("viewerPlaceholder")

            self._scene = qt_widgets.QGraphicsScene(self)
            self.view = ImageGraphicsView(self._scene, self)

            shell = qt_widgets.QWidget(self)
            shell.setObjectName("viewerShell")
            shell.setLayout(self._stack)
            self._stack.addWidget(self._placeholder)
            self._stack.addWidget(self.view)
            layout.addWidget(shell, 1)

        def set_message(self, message):
            self.image_path = None
            self._has_image = False
            self._scene.clear()
            self._pixmap_item = None
            self._placeholder.setText(message)
            self._stack.setCurrentWidget(self._placeholder)

        def set_image(self, image, *, image_path=None):
            pixmap = qt_gui.QPixmap.fromImage(image)
            self.image_path = str(image_path) if image_path else self.image_path
            self._scene.clear()
            self._pixmap_item = self._scene.addPixmap(pixmap)
            self._scene.setSceneRect(self._pixmap_item.boundingRect())
            self._has_image = True
            self._stack.setCurrentWidget(self.view)
            self.fit_image()

        def load_image(self, image_path):
            path = Path(image_path)
            if not path.is_file():
                self.set_message(f"Image not found:\n{path}")
                return
            reader = qt_gui.QImageReader(str(path))
            reader.setAutoTransform(True)
            image = reader.read()
            if image.isNull():
                self.set_message(f"Failed to load image:\n{path}\n\n{reader.errorString()}")
                return
            self.set_image(image, image_path=path)

        def has_image(self):
            return self._has_image and self._pixmap_item is not None

        def fit_image(self):
            if not self.has_image():
                return
            self.view.resetTransform()
            self.view._zoom_level = 0.0
            self.view.fitInView(self._pixmap_item, qt_core.Qt.KeepAspectRatio)

    _VIEWER_TYPES = (qt_core, qt_gui, qt_widgets, QtImageViewer)
    return _VIEWER_TYPES


def ensure_application(argv=None):
    qt_core, qt_gui, qt_widgets, _viewer_widget = viewer_types()
    app = qt_widgets.QApplication.instance()
    owns_app = app is None
    if app is None:
        app = qt_widgets.QApplication(list(argv or [sys.argv[0]]))
        app.setApplicationName("CityGen")
    return qt_core, qt_gui, qt_widgets, app, owns_app
