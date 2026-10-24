"""The app's process: one native window (WebView2, through pywebview) showing the page, and the bridge."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import threading
import traceback
import webbrowser

from config.path import APP_NAME
from gui.core import app_files
from gui.core.title_bar import set_title_bar_colors
from gui.web import server
from gui.web.bridge import Api

APP_WIDTH = 1366
APP_HEIGHT = 768
# The page's tokens (static/app.css): the window background, and the sky the title bar runs into.
APP_BG = "#f2f0ed"
SKY = "#cfe4f8"
SKY_TEXT = "#2f5274"
WEBVIEW2_DOWNLOAD = "https://developer.microsoft.com/microsoft-edge/webview2/"


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
    options = _parse_args(list(argv or []))
    try:
        import webview

        if not _has_webview2():
            _message_box(
                f"{APP_NAME} needs the Microsoft Edge WebView2 Runtime, which comes with Windows 11 and most of "
                "Windows 10. The download page opens next."
            )
            webbrowser.open(WEBVIEW2_DOWNLOAD)
            return 1

        app_files.clear_pipeline_artifacts()  # clean slate each launch; keeps exported worlds
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
            min_size=(960, 720),
            background_color=APP_BG,
        )
        if sys.platform == "win32":
            # ``native`` is the WinForms form that holds the page.
            window.events.shown += lambda: set_title_bar_colors(window.native.Handle.ToInt64(), SKY, SKY_TEXT)
        threading.Thread(target=_warm_up_renderer, daemon=True).start()
        icon = app_files.APP_ICON_PATH if os.path.isfile(app_files.APP_ICON_PATH) else None
        # Private mode (the default) keeps WebView2's data in a temp folder: writable even from the Store's install.
        webview.start(debug=options.debug, icon=icon)
        return 0
    except Exception:  # top-level crash boundary: log details and tell the user where
        try:
            with open(app_files.STARTUP_ERROR_LOG, "w", encoding="utf-8") as fh:
                fh.write(traceback.format_exc())
        except OSError:
            pass
        _message_box(f"{APP_NAME} failed to start.\n\nDetails were written to:\n{app_files.STARTUP_ERROR_LOG}")
        raise
