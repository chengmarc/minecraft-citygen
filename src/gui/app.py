"""PySide6 host shell for CityGen: main window and process entry point."""

from __future__ import annotations

import argparse
import os
import traceback

from PySide6 import QtGui, QtWidgets

from gui.core import common
from gui.widgets.qt_viewer import ensure_application
from gui.tabs import ExtractionTab, GenerationTab, PreviewTab
from gui.core.theme import configure_app_style


class CityGeneratorQtApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CityGen")
        self.resize(common.APP_WIDTH, common.APP_HEIGHT)
        self.setMinimumSize(960, 720)
        if os.path.exists(common.APP_ICON_PATH):
            self.setWindowIcon(QtGui.QIcon(common.APP_ICON_PATH))

        self._saved_gui_config = common.load_saved_gui_config()

        preview_tab = PreviewTab(self)
        generation_tab = GenerationTab(self)
        preview_tab.set_peer(generation_tab)
        generation_tab.set_peer(preview_tab)

        tabs = QtWidgets.QTabWidget(self)
        tabs.addTab(ExtractionTab(self), "Extraction")
        tabs.addTab(preview_tab, "Preview")
        tabs.addTab(generation_tab, "Generation")
        self.setCentralWidget(tabs)

    def get_saved_config_section(self, section):
        value = self._saved_gui_config.get(section)
        return value if isinstance(value, dict) else None

    def set_saved_config_section(self, section, value):
        self._saved_gui_config[section] = value
        common.save_saved_gui_config(self._saved_gui_config)


def _parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(prog="citygen", description="CityGen Qt application.")
    parser.add_argument(
        "--qt-style",
        dest="style_name",
        default=None,
        help="Qt widget style to use (default: Fusion).",
    )
    parser.add_argument(
        "--no-custom-theme",
        dest="use_custom_theme",
        action="store_false",
        help="Use the plain Qt style instead of the bundled CityGen theme.",
    )
    parser.set_defaults(use_custom_theme=True)
    # Unrecognized args (e.g. Qt platform flags) are forwarded to QApplication.
    return parser.parse_known_args(list(argv))


def main(argv: list[str] | None = None) -> int:
    options, qt_args = _parse_args(list(argv or []))

    app = ensure_application(qt_args)
    configure_app_style(app, style_name=options.style_name, use_custom_theme=options.use_custom_theme)
    try:
        window = CityGeneratorQtApp()
        window.show()
        return app.exec()
    except Exception:  # top-level crash boundary: log details and surface a dialog
        message = traceback.format_exc()
        try:
            with open(common.STARTUP_ERROR_LOG, "w", encoding="utf-8") as fh:
                fh.write(message)
        except OSError:
            pass
        QtWidgets.QMessageBox.critical(
            None,
            "CityGen",
            f"GUI startup failed.\n\nDetails were written to:\n{common.STARTUP_ERROR_LOG}",
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
