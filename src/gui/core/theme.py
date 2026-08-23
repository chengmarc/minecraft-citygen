"""Application styling: stylesheet, palette, and widget-decoration helpers."""

from __future__ import annotations

import os

from PySide6 import QtGui, QtWidgets

from gui.core import common

# Brand palette. ACCENT_RGB is the accent (#0d6efd) used throughout
# APP_STYLESHEET, kept here for constructing QColor objects in code.
ACCENT_RGB = (13, 110, 253)
SHADOW_RGB = (23, 32, 43)

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
    shadow.setColor(QtGui.QColor(*SHADOW_RGB, 80))
    button.setGraphicsEffect(shadow)


def apply_button_icon(button, icon_name: str) -> None:
    icon_path = os.path.join(common.ICON_DIR, icon_name)
    if not os.path.exists(icon_path):
        return
    label = button.text().strip()
    button.setText(f" {label}" if label else label)
    pixmap = QtGui.QPixmap(icon_path)
    button.setIcon(QtGui.QIcon(pixmap))
    if not pixmap.isNull():
        button.setIconSize(pixmap.size())
    # Capture the original point size once so repeated calls stay idempotent
    # (scaling relative to the current font would compound on every call).
    font = button.font()
    base = button.property("_baseFontSize")
    if base is None:
        base = font.pointSizeF() if font.pointSizeF() > 0 else float(font.pointSize())
        button.setProperty("_baseFontSize", base)
    if base > 0:
        font.setPointSizeF(base * 1.5)
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
    families = set(QtGui.QFontDatabase.families())
    for family in ("SF Pro Text", "Segoe UI Variable", "Segoe UI", "Inter", "Arial"):
        if family in families:
            app.setFont(QtGui.QFont(family, 10))
            break
