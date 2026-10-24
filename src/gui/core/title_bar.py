"""The native title bar: its colours, so the window's top runs into the page's tab row, and no title or icon in it,
since the page's header shows both."""

from __future__ import annotations

import ctypes
import sys

# DwmSetWindowAttribute attributes for the title bar's colours (Windows 11 and later).
_DWMWA_BORDER_COLOR = 34
_DWMWA_CAPTION_COLOR = 35
_DWMWA_TEXT_COLOR = 36

# SetWindowThemeAttribute: what the title bar leaves out.
_WTA_NONCLIENT = 1
_WTNCA_NODRAWCAPTION = 0x1
_WTNCA_NODRAWICON = 0x2


_WM_SETICON = 0x0080
_ICON_SMALL = 0


class _WtaOptions(ctypes.Structure):
    _fields_ = [("dwFlags", ctypes.c_uint32), ("dwMask", ctypes.c_uint32)]


_blank_icon = None   # kept for the process's life: the window draws it


def _blank_small_icon():
    """A 16x16 icon that's all transparent: AND mask all ones, colour bits all zeros."""
    global _blank_icon
    if _blank_icon is None:
        user32 = ctypes.windll.user32
        user32.CreateIcon.restype = ctypes.c_void_p
        and_mask = (ctypes.c_ubyte * 32)(*([0xFF] * 32))
        xor_mask = (ctypes.c_ubyte * 32)()
        _blank_icon = user32.CreateIcon(None, 16, 16, 1, 1, and_mask, xor_mask)
    return _blank_icon


def hide_title_and_icon(hwnd: int) -> None:
    """Leave the title and icon out of window ``hwnd``'s title bar.

    The window keeps both: the taskbar, Alt+Tab and Task Manager still show them.
    Windows 11 honours the theme's "no caption" but not its "no icon", so the
    title bar's own icon, the small one, is also swapped for a blank; the
    taskbar and Alt+Tab show the big one.
    """
    if sys.platform != "win32":
        return
    flags = _WTNCA_NODRAWCAPTION | _WTNCA_NODRAWICON
    options = _WtaOptions(flags, flags)
    try:
        ctypes.windll.uxtheme.SetWindowThemeAttribute(
            ctypes.c_void_p(hwnd), _WTA_NONCLIENT, ctypes.byref(options), ctypes.sizeof(options),
        )
        blank = _blank_small_icon()
        if blank:
            ctypes.windll.user32.SendMessageW(
                ctypes.c_void_p(hwnd), _WM_SETICON, ctypes.c_size_t(_ICON_SMALL), ctypes.c_void_p(blank),
            )
    except (AttributeError, OSError):  # boundary: no uxtheme or user32
        pass


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
