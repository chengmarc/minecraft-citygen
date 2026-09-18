"""PySide6 host shell for Minecraft CityGen: main window and process entry point."""

from __future__ import annotations

import argparse
import os
import traceback

from PySide6 import QtGui, QtWidgets

from gui.core import app_files
from gui.widgets.qt_viewer import ensure_application
from gui.tabs.extraction import ExtractionTab
from gui.tabs.generation import GenerationTab
from gui.tabs.preview import PreviewTab
from gui.core.theme import configure_app_style

APP_WIDTH = 1366
APP_HEIGHT = 768


class CityGeneratorQtApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minecraft CityGen")
        self.resize(APP_WIDTH, APP_HEIGHT)
        self.setMinimumSize(960, 720)
        if os.path.exists(app_files.APP_ICON_PATH):
            self.setWindowIcon(QtGui.QIcon(app_files.APP_ICON_PATH))

        self._saved_gui_config = app_files.load_saved_gui_config()
        app_files.clear_pipeline_artifacts()  # clean slate each launch; keeps exported worlds

        self.preview_tab = PreviewTab(self)
        self.generation_tab = GenerationTab(self)
        self.preview_tab.set_peer(self.generation_tab)
        self.generation_tab.set_peer(self.preview_tab)
        self.extraction_tab = ExtractionTab(self)

        tabs = QtWidgets.QTabWidget(self)
        extraction_index = tabs.addTab(self.extraction_tab, "Extract")
        preview_index = tabs.addTab(self.preview_tab, "Preview")
        generation_index = tabs.addTab(self.generation_tab, "Build")
        tab_bar = tabs.tabBar()
        tab_bar.setTabToolTip(
            extraction_index,
            "Step 1 of 3: Choose a Minecraft world and extract road, house, and landmark assets.",
        )
        tab_bar.setTabToolTip(
            preview_index,
            "Step 2 of 3: Test seeds and Avenue/Street settings before the final build.",
        )
        tab_bar.setTabToolTip(
            generation_index,
            "Step 3 of 3: Build the city, render it, and export the Minecraft world.",
        )
        self.setCentralWidget(tabs)
        self.refresh_prerequisite_buttons()

    def get_saved_config_section(self, section):
        value = self._saved_gui_config.get(section)
        return value if isinstance(value, dict) else None

    def set_saved_config_section(self, section, value):
        self._saved_gui_config[section] = value
        app_files.save_saved_gui_config(self._saved_gui_config)

    def refresh_prerequisite_buttons(self):
        """Re-gate Preview/Build on extracted assets; call after artifacts change."""
        self.preview_tab.refresh_prerequisite_state()
        self.generation_tab.refresh_prerequisite_state()


def _parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(prog="citygen", description="Minecraft CityGen Qt application.")
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
        help="Use the plain Qt style instead of the bundled Minecraft CityGen theme.",
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
            with open(app_files.STARTUP_ERROR_LOG, "w", encoding="utf-8") as fh:
                fh.write(message)
        except OSError:
            pass
        QtWidgets.QMessageBox.critical(
            None,
            "Minecraft CityGen",
            f"GUI startup failed.\n\nDetails were written to:\n{app_files.STARTUP_ERROR_LOG}",
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
