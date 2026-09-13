"""Application styling: stylesheet, palette, and widget-decoration helpers."""

from __future__ import annotations

import os

from PySide6 import QtCore, QtGui, QtWidgets

from gui.core import common

# Design tokens for the Qt widget stylesheet. Keep colors semantic so the QSS
# reads like a small design system instead of a pile of one-off hex values.
COLOR = {
    "app_bg": "#edf2f7",
    "content_bg": "#e5edf7",
    "surface": "#ffffff",
    "surface_alt": "#f8fbff",
    "surface_panel": "#eef5fc",
    "surface_muted": "#d9e3ef",
    "surface_sunken": "#cfdae8",
    "viewer_bg": "#d7e4f2",
    "border": "#d1dbe8",
    "border_strong": "#a7b6c8",
    "text": "#17202b",
    "text_soft": "#334155",
    "muted": "#657386",
    "accent": "#1f5ed5",
    "accent_hover": "#184fb8",
    "accent_pressed": "#123d91",
    "accent_soft": "#dbe8ff",
    "accent_border": "#7ea2ee",
    "accent_disabled": "#b8c4d6",
    "button": "#dce8f7",
    "button_hover": "#cdddf3",
    "button_pressed": "#b9cee9",
    "disabled": "#e4e9f1",
    "disabled_text": "#ffffff",
    "success_bg": "#dff4e8",
    "success_border": "#afdcbc",
    "success_text": "#1c6a45",
}

RADIUS = {
    "sm": 4,
    "md": 6,
    "lg": 8,
}

CONTROL_HEIGHT = 22
BIG_CONTROL_HEIGHT = 34
NORMAL_BUTTON_FONT_SIZE = 10
BIG_BUTTON_FONT_SIZE = 16
STATUS_CHIP_FONT_SIZE = 11
ICON_BUTTON_FONT_SCALE = 1.8

# ACCENT_RGB is kept for non-QSS drawing code such as selection overlays.
ACCENT_RGB = (36, 87, 197)
SHADOW_RGB = (23, 32, 43)
BIG_BUTTON_WIDTH = 158

APP_STYLESHEET = f"""
QMainWindow, QDialog {{
    background: {COLOR["app_bg"]};
    color: {COLOR["text"]};
    selection-background-color: {COLOR["accent"]};
    selection-color: white;
}}

QWidget {{
    background: {COLOR["app_bg"]};
    color: {COLOR["text"]};
}}

QLabel {{
    background: transparent;
}}

QTabWidget {{
    background: {COLOR["app_bg"]};
}}

QTabBar {{
    background: {COLOR["app_bg"]};
}}

QTabWidget::pane {{
    border: 0;
    border-radius: {RADIUS["lg"]}px;
    background: {COLOR["content_bg"]};
}}

QTabBar::tab {{
    background: {COLOR["surface_muted"]};
    color: {COLOR["text_soft"]};
    border: 1px solid {COLOR["border"]};
    border-bottom-color: {COLOR["surface_muted"]};
    border-top-left-radius: {RADIUS["md"]}px;
    border-top-right-radius: {RADIUS["md"]}px;
    padding: 10px 20px;
    margin-right: 6px;
    font-weight: 650;
}}

QTabBar::tab:first {{
    margin-left: 8px;
}}

QTabBar::tab:hover {{
    background: {COLOR["accent_soft"]};
    color: {COLOR["accent_pressed"]};
}}

QTabBar::tab:selected {{
    background: {COLOR["surface"]};
    color: {COLOR["accent"]};
    border-color: {COLOR["border"]};
    border-bottom-color: {COLOR["surface"]};
    font-weight: 750;
}}

QGroupBox {{
    border: 1px solid {COLOR["border"]};
    border-radius: {RADIUS["lg"]}px;
    margin-top: 14px;
    font-weight: 600;
    background: {COLOR["surface_panel"]};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: {COLOR["text_soft"]};
    background: {COLOR["surface_panel"]};
}}

QLineEdit, QComboBox, QSpinBox {{
    border: 1px solid {COLOR["border_strong"]};
    border-radius: {RADIUS["md"]}px;
    padding: 8px 8px;
    min-height: 22px;
    background: {COLOR["surface"]};
    color: {COLOR["text"]};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 2px solid {COLOR["accent"]};
    background: {COLOR["surface"]};
}}

QLineEdit[readOnly="true"] {{
    background: {COLOR["surface_panel"]};
    color: {COLOR["muted"]};
}}

QComboBox::drop-down {{
    border: 0;
    width: 26px;
}}

QPushButton {{
    border: 1px solid {COLOR["border"]};
    border-radius: {RADIUS["md"]}px;
    padding: 8px 16px;
    min-height: {CONTROL_HEIGHT}px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {COLOR["surface_panel"]}, stop:1 {COLOR["button"]});
    color: {COLOR["accent_pressed"]};
    font-size: {NORMAL_BUTTON_FONT_SIZE}pt;
    font-weight: 700;
}}

QPushButton:hover {{
    background: {COLOR["button_hover"]};
    border-color: {COLOR["accent_border"]};
}}

QPushButton:pressed {{
    background: {COLOR["button_pressed"]};
}}

QPushButton:focus {{
    border: 2px solid {COLOR["accent"]};
}}

QPushButton#primaryButton,
QPushButton[bigButton="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3778ee, stop:1 {COLOR["accent"]});
    border-color: {COLOR["accent"]};
    color: white;
    font-size: {BIG_BUTTON_FONT_SIZE}pt;
    min-height: {BIG_CONTROL_HEIGHT}px;
}}

QPushButton#primaryButton:hover,
QPushButton[bigButton="true"]:hover {{
    background: {COLOR["accent_hover"]};
    border-color: {COLOR["accent_hover"]};
}}

QPushButton#primaryButton:pressed,
QPushButton[bigButton="true"]:pressed {{
    background: {COLOR["accent_pressed"]};
    border-color: {COLOR["accent_pressed"]};
}}

QPushButton:disabled {{
    background: {COLOR["disabled"]};
    border-color: {COLOR["disabled"]};
    color: {COLOR["disabled_text"]};
}}

QPushButton#primaryButton:disabled,
QPushButton[bigButton="true"]:disabled {{
    background: {COLOR["accent_disabled"]};
    border-color: {COLOR["accent_disabled"]};
    color: {COLOR["disabled_text"]};
}}

QSlider::groove:horizontal {{
    height: 6px;
    border-radius: 3px;
    background: {COLOR["surface_sunken"]};
}}

QSlider::handle:horizontal {{
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
    background: {COLOR["accent"]};
}}

QSlider::handle:horizontal:hover {{
    background: {COLOR["accent_hover"]};
}}

QProgressBar {{
    border: 1px solid {COLOR["border"]};
    border-radius: {RADIUS["sm"]}px;
    background: {COLOR["surface_muted"]};
    height: 12px;
    text-align: center;
}}

QProgressBar::chunk {{
    border-radius: {RADIUS["sm"]}px;
    background: {COLOR["accent"]};
}}

QLabel#statusLabel {{
    color: {COLOR["muted"]};
}}

QLabel#sectionIntro {{
    color: {COLOR["text_soft"]};
    padding: 10px 0 6px 0;
}}

QLabel#subtleLabel, QLabel#summaryLabel {{
    color: {COLOR["muted"]};
}}

QGroupBox#extractionAreaCard {{
    border: 1px solid {COLOR["border"]};
    border-radius: {RADIUS["lg"]}px;
    margin-top: 0;
    background: {COLOR["surface_alt"]};
}}

QGroupBox#extractionAreaCard::title {{
    subcontrol-origin: margin;
    left: -9999px;
    width: 0;
    color: transparent;
    padding: 0;
}}

QLabel#cardTitle {{
    font-size: 14px;
    font-weight: 700;
    color: {COLOR["text"]};
}}

QLabel#cardDetail {{
    color: {COLOR["muted"]};
}}

QLabel#statusChip {{
    min-width: 106px;
    padding: 5px 12px;
    border-radius: {RADIUS["sm"]}px;
    border: 1px solid {COLOR["border"]};
    background: {COLOR["surface_muted"]};
    color: {COLOR["muted"]};
    font-size: {STATUS_CHIP_FONT_SIZE}pt;
    font-weight: 700;
}}

QLabel#statusChip[selected="true"] {{
    border-color: {COLOR["success_border"]};
    background: {COLOR["success_bg"]};
    color: {COLOR["success_text"]};
}}

QToolButton#advancedToggle {{
    border: 1px solid {COLOR["border"]};
    border-radius: {RADIUS["md"]}px;
    padding: 8px 16px;
    min-height: {CONTROL_HEIGHT}px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {COLOR["surface_panel"]}, stop:1 {COLOR["button"]});
    color: {COLOR["accent_pressed"]};
    font-weight: 700;
}}

QToolButton#advancedToggle:hover {{
    background: {COLOR["button_hover"]};
    border-color: {COLOR["accent_border"]};
}}

QToolButton#advancedToggle:pressed {{
    background: {COLOR["button_pressed"]};
}}

QToolButton#advancedToggle:checked {{
    background: {COLOR["accent_soft"]};
    border-color: {COLOR["accent"]};
    color: {COLOR["accent"]};
}}

QToolButton#advancedToggle:checked:hover {{
    background: {COLOR["surface_alt"]};
}}

QToolButton#advancedToggle:disabled {{
    background: {COLOR["disabled"]};
    border-color: {COLOR["disabled"]};
    color: {COLOR["disabled_text"]};
}}

QFrame#qtImageViewer {{
    border: 1px solid {COLOR["border"]};
    border-radius: {RADIUS["lg"]}px;
    background: {COLOR["viewer_bg"]};
}}

QWidget#viewerShell {{
    background: {COLOR["viewer_bg"]};
    border-radius: {RADIUS["md"]}px;
}}

QLabel#viewerTitle {{
    font-size: 14px;
    font-weight: 700;
    color: {COLOR["text"]};
}}

QLabel#viewerPlaceholder {{
    color: {COLOR["muted"]};
    padding: 16px;
}}
"""


def style_button(button) -> None:
    button.setCursor(QtCore.Qt.PointingHandCursor)
    is_big_action = button.objectName() == "primaryButton" or button.property("bigButton")
    if is_big_action:
        button.setFixedWidth(BIG_BUTTON_WIDTH)
    shadow = QtWidgets.QGraphicsDropShadowEffect(button)
    shadow.setBlurRadius(18)
    shadow.setOffset(0, 4)
    shadow.setColor(QtGui.QColor(*SHADOW_RGB, 58))
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
        font.setPointSizeF(base * ICON_BUTTON_FONT_SCALE)
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
