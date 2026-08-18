"""GUI application shell and entry point."""

from __future__ import annotations

import traceback
import tkinter as tk
from tkinter import messagebox, ttk

from clear_cache import purge_artifacts
from gui import common
from gui.theme import configure_app_style
from gui.tabs import CityTab, ExtractionTab, PreviewTab
from gui.widgets import ActionButton


class CityGeneratorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.ui_font_family = common.pick_ui_font(self)
        self.title("Minecraft City Generator")
        self.geometry(f"{common.APP_WIDTH}x{common.APP_HEIGHT}")

        theme_bg = configure_app_style(self, self.ui_font_family)
        self.configure(bg=theme_bg)

        shell = ttk.Frame(self, style="Page.TFrame", padding=10)
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(shell, style="Page.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        toolbar.columnconfigure(0, weight=1)
        ActionButton(
            toolbar,
            text="Clear Artifacts",
            command=self._clear_artifacts,
            width=max(common.BUTTON_WIDTH + 4, 15),
        ).grid(row=0, column=1, sticky="e")

        notebook = ttk.Notebook(shell, style="App.TNotebook")
        notebook.grid(row=1, column=0, sticky="nsew")
        self.notebook = notebook
        self._tab_builders = {
            "Extraction": ExtractionTab,
            "Preview": PreviewTab,
            "Render": CityTab,
        }
        self._tab_frames = {}
        self._loaded_tabs = set()
        for title in self._tab_builders:
            frame = ttk.Frame(notebook, style="Page.TFrame")
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)
            notebook.add(frame, text=title)
            self._tab_frames[title] = frame
        notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed, add="+")
        self._load_tab("Extraction")
        self.update_idletasks()
        self.deiconify()

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

    def _clear_artifacts(self):
        confirm = messagebox.askyesno(
            "Clear artifacts",
            "Delete generated pipeline artifacts in this repo and exported city schematics in the WorldEdit folder?",
        )
        if not confirm:
            return
        try:
            removed = purge_artifacts()
        except Exception as exc:
            messagebox.showerror("Clear artifacts failed", str(exc))
            return
        messagebox.showinfo("Artifacts cleared", f"Removed {len(removed)} artifact(s).")


def main():
    try:
        app = CityGeneratorApp()
        app.mainloop()
    except Exception:
        message = traceback.format_exc()
        try:
            with open(common.STARTUP_ERROR_LOG, "w", encoding="utf-8") as fh:
                fh.write(message)
        except Exception:
            pass
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None,
                f"GUI startup failed.\n\nDetails were written to:\n{common.STARTUP_ERROR_LOG}",
                "Minecraft City Generator",
                0x10,
            )
        except Exception:
            pass
        raise
