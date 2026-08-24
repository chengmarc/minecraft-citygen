"""PySide6 host shell for CityGen: main window and process entry point."""

from __future__ import annotations

import argparse
import copy
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
        self._completed_extraction_state = None
        self._extraction_run_active = False
        common.clear_pipeline_artifacts()  # clean slate each launch; keeps exported worlds

        self.preview_tab = PreviewTab(self)
        self.generation_tab = GenerationTab(self)
        self.preview_tab.set_peer(self.generation_tab)
        self.generation_tab.set_peer(self.preview_tab)
        self.extraction_tab = ExtractionTab(self)

        tabs = QtWidgets.QTabWidget(self)
        extraction_index = tabs.addTab(self.extraction_tab, "Extract Assets")
        preview_index = tabs.addTab(self.preview_tab, "Preview Layout")
        generation_index = tabs.addTab(self.generation_tab, "Build City")
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
        common.save_saved_gui_config(self._saved_gui_config)

    def _refresh_after_gui_change(self, *_args):
        self.refresh_prerequisite_buttons()

    note_preview_inputs_changed = _refresh_after_gui_change

    def _current_extraction_state(self):
        tab = getattr(self, "extraction_tab", None)
        if tab is None:
            return None
        return tab.prerequisite_state()

    def note_extraction_inputs_changed(self):
        current = self._current_extraction_state()
        if self._completed_extraction_state is not None and current != self._completed_extraction_state:
            self._completed_extraction_state = None
        self.refresh_prerequisite_buttons()

    def begin_extraction_run(self):
        self._extraction_run_active = True
        self._completed_extraction_state = None
        self.refresh_prerequisite_buttons()

    def mark_extraction_complete(self, state):
        self._extraction_run_active = False
        self._completed_extraction_state = copy.deepcopy(state)
        self.refresh_prerequisite_buttons()

    def end_extraction_run(self, succeeded):
        self._extraction_run_active = False
        if not succeeded:
            self.refresh_prerequisite_buttons()

    def _assets_ready(self):
        if self._extraction_run_active:
            return False
        current = self._current_extraction_state()
        if self._completed_extraction_state is not None:
            return current == self._completed_extraction_state
        return common.extracted_assets_ready()

    preview_prerequisite_met = _assets_ready
    generation_prerequisite_met = _assets_ready

    def refresh_prerequisite_buttons(self):
        for tab in (getattr(self, "preview_tab", None), getattr(self, "generation_tab", None)):
            if tab is not None and hasattr(tab, "refresh_prerequisite_state"):
                tab.refresh_prerequisite_state()


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
