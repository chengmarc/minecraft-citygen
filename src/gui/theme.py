"""Minimal theme helpers for the Tk application shell."""

from __future__ import annotations

from tkinter import ttk


def configure_app_style(app, _ui_font_family: str) -> str:
    style = ttk.Style(app)
    try:
        style.theme_use("vista")
    except Exception:
        pass
    return app.cget("bg")
