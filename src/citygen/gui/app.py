"""The app's process: one native window (WebView2, through pywebview) showing the page, and the bridge.

The installed ``citygen`` entry point; src/application.pyw runs it from a checkout and in the release build.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import sys
import threading
import traceback
import webbrowser

from citygen.gui import files, server
from citygen.gui.bridge import Api
from citygen.paths import APP_ICON, APP_NAME

# The window opens at its smallest size, and can only grow from there.
APP_WIDTH = 1280
APP_HEIGHT = 800
WEBVIEW2_DOWNLOAD = "https://developer.microsoft.com/microsoft-edge/webview2/"


# --- The native title bar: the sky's colours, and no title or icon, which the page's header shows

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


def page_colors(*tokens):
    """The page's colour tokens (``--app-bg`` and the like, in static/tokens.css), so the window matches the page."""
    css = (server.STATIC / "tokens.css").read_text(encoding="utf-8")
    return [re.search(rf"--{token}:\s*(#[0-9a-fA-F]{{6}})\s*;", css).group(1) for token in tokens]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="citygen", description="MC CityGen application.")
    parser.add_argument("--debug", action="store_true", help="Allow the page's developer tools (F12).")
    return parser.parse_args(argv)


def _message_box(text: str) -> None:
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, 0x30)  # MB_ICONWARNING
    else:
        print(text, file=sys.stderr)


def _has_webview2() -> bool:
    """Whether pywebview will use WebView2. Without it, it falls back to MSHTML (IE11), which can't run the page."""
    if sys.platform != "win32":
        return True
    from webview.platforms import winforms

    return winforms.renderer == "edgechromium"


def _warm_up_renderer():
    """Pay the isometric renderer's numba import/JIT cost off the UI thread.

    Otherwise the first extraction stalls at the start of its render step.
    A failure here is ignored: the real render reports it.
    """
    try:
        from engine.render.isometric import warm_up

        warm_up()
    except Exception:  # boundary: warm-up is best-effort
        pass


def main(argv: list[str] | None = None) -> int:
    options = _parse_args(sys.argv[1:] if argv is None else list(argv))
    try:
        import webview

        if not _has_webview2():
            _message_box(
                f"{APP_NAME} needs the Microsoft Edge WebView2 Runtime, which comes with Windows 11 and most of "
                "Windows 10. The download page opens next."
            )
            webbrowser.open(WEBVIEW2_DOWNLOAD)
            return 1

        files.clear_pipeline_artifacts()  # clean slate each launch; keeps exported worlds
        # The window behind the page, and the sky the title bar runs into.
        app_bg, sky, sky_text = page_colors("app-bg", "sky", "sky-text")
        window = None

        def emit(event, payload):
            window.evaluate_js(f"citygen.receive({json.dumps(event)}, {json.dumps(payload)})")

        def pick_folder(initial):
            chosen = window.create_file_dialog(webview.FileDialog.FOLDER, directory=initial or "")
            return chosen[0] if chosen else None

        window = webview.create_window(
            APP_NAME,
            url=server.app,
            js_api=Api(emit, pick_folder=pick_folder),
            width=APP_WIDTH,
            height=APP_HEIGHT,
            min_size=(APP_WIDTH, APP_HEIGHT),
            background_color=app_bg,
        )
        if sys.platform == "win32":
            # ``native`` is the WinForms form that holds the page.
            def style_title_bar():
                hwnd = window.native.Handle.ToInt64()
                set_title_bar_colors(hwnd, sky, sky_text)
                hide_title_and_icon(hwnd)   # the page's header shows both

            window.events.shown += style_title_bar
        threading.Thread(target=_warm_up_renderer, daemon=True).start()
        icon = APP_ICON if os.path.isfile(APP_ICON) else None
        # Private mode (the default) keeps WebView2's data in a temp folder: writable even from the Store's install.
        webview.start(debug=options.debug, icon=icon)
        return 0
    except Exception:  # top-level crash boundary: log details and tell the user where
        try:
            with open(files.STARTUP_ERROR_LOG, "w", encoding="utf-8") as fh:
                fh.write(traceback.format_exc())
        except OSError:
            pass
        _message_box(f"{APP_NAME} failed to start.\n\nDetails were written to:\n{files.STARTUP_ERROR_LOG}")
        raise
