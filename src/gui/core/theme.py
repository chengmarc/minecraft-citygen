"""Application styling: stylesheet, palette, and widget-decoration helpers."""

from __future__ import annotations

import ctypes
import os
import sys

from PySide6 import QtCore, QtGui, QtWidgets

from gui.core import app_files

# Design tokens for the Qt widget stylesheet. Keep colors semantic so the QSS
# reads like a small design system instead of a pile of one-off hex values.
#
# The window is layered like the app icon: sky blue at the top (the strip behind
# the tabs), grass green in the middle (everything you act on: buttons, the
# selected tab, focus), and dirt brown at the bottom (the progress bar, on the
# faint brown ground of the window). New colors should follow the same layers.
COLOR = {
    # Sky: the tab row along the top of the window.
    "sky": "#cfe4f8",
    "sky_tab": "#e6f1fc",
    "sky_tab_hover": "#f4f9fe",
    "sky_border": "#aecbe8",
    "sky_text": "#2f5274",
    # The faintest dirt brown for the window and its panels: nearly gray, just warm, so the green actions stand out.
    "app_bg": "#f2f0ed",
    "content_bg": "#e9e6e2",
    "surface": "#ffffff",
    "surface_alt": "#faf9f7",
    "surface_panel": "#f5f3f0",
    "surface_muted": "#e1ded8",
    "surface_sunken": "#d2cec8",
    "viewer_bg": "#ffffff",
    "border": "#d9d4ce",
    "border_strong": "#b2aca4",
    "text": "#2a221a",
    "text_soft": "#4a3e32",
    "muted": "#7a6d60",
    # Grass green for the actions: the app icon's, deep enough for white text.
    "accent_top": "#5cbf2a",
    "accent": "#3d921d",
    "accent_hover": "#327c16",
    "accent_pressed": "#26620f",
    "accent_soft": "#e2f3d5",
    "accent_border": "#93cf6c",
    "accent_disabled": "#c8d3bb",
    # The smaller buttons are grass green too, at their own size.
    "button_top": "#5cbf2a",
    "button": "#3d921d",
    "button_hover": "#327c16",
    "button_pressed": "#26620f",
    "button_text": "#ffffff",
    "disabled": "#e5e2de",
    "disabled_text": "#ffffff",
    "success_bg": "#e2f3d5",
    "success_border": "#a9d98a",
    "success_text": "#2d6a12",
    # Dirt: the bottom of the window, the progress bar.
    "dirt_top": "#b67a3f",
    "dirt": "#8b5a2b",
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
ACCENT_RGB = (61, 146, 29)
SHADOW_RGB = (42, 32, 22)
BIG_BUTTON_WIDTH = 158

APP_STYLESHEET = f"""
QMainWindow, QDialog {{
    color: {COLOR["text"]};
    selection-background-color: {COLOR["accent"]};
    selection-color: white;
}}

QWidget {{
    background: {COLOR["app_bg"]};
    color: {COLOR["text"]};
}}

/* The sky: the window's own colour, which only the tab row shows, since the tab pages cover the rest. After the
   QWidget rule, which would otherwise paint over it. */
QMainWindow {{
    background: {COLOR["sky"]};
}}

QLabel {{
    background: transparent;
}}

QTabWidget, QTabBar {{
    background: transparent;
}}

QTabWidget::pane {{
    border: 0;
    border-radius: {RADIUS["lg"]}px;
    background: {COLOR["content_bg"]};
}}

QTabBar::tab {{
    background: {COLOR["sky_tab"]};
    color: {COLOR["sky_text"]};
    border: 1px solid {COLOR["sky_border"]};
    border-bottom-color: {COLOR["sky_border"]};
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
    background: {COLOR["sky_tab_hover"]};
}}

/* The front tab is the page's own colour, so it opens into the page below. */
QTabBar::tab:selected {{
    background: {COLOR["app_bg"]};
    color: {COLOR["accent"]};
    border-color: {COLOR["sky_border"]};
    border-bottom-color: {COLOR["app_bg"]};
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
        stop:0 {COLOR["button_top"]}, stop:1 {COLOR["button"]});
    color: {COLOR["button_text"]};
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
        stop:0 {COLOR["accent_top"]}, stop:1 {COLOR["accent"]});
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
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {COLOR["dirt_top"]}, stop:1 {COLOR["dirt"]});
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
        stop:0 {COLOR["button_top"]}, stop:1 {COLOR["button"]});
    color: {COLOR["button_text"]};
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
    if not is_big_action:
        button.setGraphicsEffect(None)
        return
    shadow = QtWidgets.QGraphicsDropShadowEffect(button)
    shadow.setBlurRadius(18)
    shadow.setOffset(0, 4)
    shadow.setColor(QtGui.QColor(*SHADOW_RGB, 58))
    button.setGraphicsEffect(shadow)


def apply_button_icon(button, icon_name: str) -> None:
    icon_path = os.path.join(app_files.ICON_DIR, icon_name)
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


# DwmSetWindowAttribute attributes for the title bar's colours (Windows 11 and later).
_DWMWA_BORDER_COLOR = 34
_DWMWA_CAPTION_COLOR = 35
_DWMWA_TEXT_COLOR = 36


def apply_title_bar_color(window) -> None:
    """Paint the window's native title bar in the sky colour, so it runs into the tab row below it.

    Windows 11 only; older Windows and other systems keep their own title bar.
    """
    if sys.platform != "win32":
        return

    def colorref(color: str) -> ctypes.c_uint:  # COLORREF is 0x00BBGGRR
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
        return ctypes.c_uint(r | g << 8 | b << 16)

    try:
        hwnd = ctypes.c_void_p(int(window.winId()))
        for attribute, color in (
            (_DWMWA_CAPTION_COLOR, COLOR["sky"]),
            (_DWMWA_BORDER_COLOR, COLOR["sky"]),
            (_DWMWA_TEXT_COLOR, COLOR["sky_text"]),
        ):
            value = colorref(color)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
    except (AttributeError, OSError):  # boundary: no dwmapi, or an older Windows without these attributes
        pass


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
