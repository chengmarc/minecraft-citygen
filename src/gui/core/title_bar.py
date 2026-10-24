"""The native title bar's colours, so the window's top runs into the page's tab row."""

from __future__ import annotations

import ctypes
import sys

# DwmSetWindowAttribute attributes for the title bar's colours (Windows 11 and later).
_DWMWA_BORDER_COLOR = 34
_DWMWA_CAPTION_COLOR = 35
_DWMWA_TEXT_COLOR = 36


def set_title_bar_colors(hwnd: int, caption: str, text: str) -> None:
    """Paint the title bar and border of window ``hwnd`` in ``caption``, with its title in ``text``.

    Windows 11 only; older Windows and other systems keep their own title bar.
    """
    if sys.platform != "win32":
        return

    def colorref(color: str) -> ctypes.c_uint:  # COLORREF is 0x00BBGGRR
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
        return ctypes.c_uint(r | g << 8 | b << 16)

    try:
        handle = ctypes.c_void_p(hwnd)
        for attribute, color in (
            (_DWMWA_CAPTION_COLOR, caption),
            (_DWMWA_BORDER_COLOR, caption),
            (_DWMWA_TEXT_COLOR, text),
        ):
            value = colorref(color)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(handle, attribute, ctypes.byref(value), ctypes.sizeof(value))
    except (AttributeError, OSError):  # boundary: no dwmapi, or an older Windows without these attributes
        pass
