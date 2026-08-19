"""GUI application shell and entry point."""

from __future__ import annotations

import os
import traceback
import tkinter as tk

import ttkbootstrap as ttk

from gui import common
from gui.theme import configure_app_style
from gui.tabs import CityTab, ExtractionTab, PreviewTab


class CityGeneratorApp(ttk.Window):
    def __init__(self):
        super().__init__(
            title="CityGen",
            theme=common.GUI_THEME,
            default_button="neutral",
            iconphoto=None,
            size=(common.APP_WIDTH, common.APP_HEIGHT),
            minsize=(960, 720),
        )
        self.withdraw()
        self._app_icon = None
        self._saved_gui_config = common.load_saved_gui_config()
        self.ui_font_family = common.pick_ui_font(self)
        self._configure_icon()

        configure_app_style(self, self.ui_font_family)

        self.notebook = ttk.Notebook(self, bootstyle="primary")
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self._tab_builders = {
            "Extraction": ExtractionTab,
            "Preview": PreviewTab,
            "Render": CityTab,
        }
        self._tab_frames = {}
        self._loaded_tabs = set()

        for title in self._tab_builders:
            frame = ttk.Frame(self.notebook, padding=4)
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)
            self.notebook.add(frame, text=title)
            self._tab_frames[title] = frame

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed, add="+")
        self._load_tab("Extraction")
        self.update_idletasks()
        self.deiconify()
        self.after(0, self._center_window)

    def _tab_title(self, tab_id):
        return self.notebook.tab(tab_id, "text")

    def _load_tab(self, title):
        if title in self._loaded_tabs:
            return
        frame = self._tab_frames[title]
        tab = self._tab_builders[title](frame)
        tab.grid(row=0, column=0, sticky="nsew")
        self._loaded_tabs.add(title)

    def _on_tab_changed(self, _event=None):
        self._load_tab(self._tab_title(self.notebook.select()))

    def get_saved_config_section(self, section):
        value = self._saved_gui_config.get(section)
        return value if isinstance(value, dict) else None

    def set_saved_config_section(self, section, value):
        self._saved_gui_config[section] = value
        common.save_saved_gui_config(self._saved_gui_config)

    def _configure_icon(self):
        if not os.path.exists(common.APP_ICON_PATH):
            return
        try:
            self._app_icon = tk.PhotoImage(file=common.APP_ICON_PATH)
            self.iconphoto(True, self._app_icon)
        except tk.TclError:
            self._app_icon = None

    def _center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = max((screen_width - width) // 2, 0)
        y = max((screen_height - height) // 2, 0)
        self.geometry(f"{width}x{height}+{x}+{y}")


def main():
    try:
        app = CityGeneratorApp()
        app.mainloop()
    except Exception:  # top-level crash boundary: log the traceback, notify, then re-raise
        message = traceback.format_exc()
        try:
            with open(common.STARTUP_ERROR_LOG, "w", encoding="utf-8") as fh:
                fh.write(message)
        except OSError:
            pass
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None,
                f"GUI startup failed.\n\nDetails were written to:\n{common.STARTUP_ERROR_LOG}",
                "CityGen",
                0x10,
            )
        except (OSError, AttributeError):
            pass
        raise
