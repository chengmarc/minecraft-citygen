"""Theme helpers for the Tk application shell."""

from __future__ import annotations

from tkinter import ttk

from gui import common


def configure_app_style(app, ui_font_family: str) -> str:
    style = ttk.Style(app)
    style.theme_use(common.GUI_THEME)

    frame_bg = common.resolve_color(app, style.lookup("TFrame", "background"), "#f3f6fb")
    label_fg = style.lookup("TLabel", "foreground") or common.TEXT

    style.configure(".", font=common.ui_font(ui_font_family, 10), foreground=label_fg)
    style.configure("Page.TFrame", background=frame_bg)
    style.configure("Card.TFrame", background=frame_bg)
    style.configure("TLabel", background=frame_bg, foreground=label_fg)
    style.configure("App.TNotebook", background=frame_bg)
    style.configure("TNotebook.Tab", padding=(12, 6), font=common.ui_font(ui_font_family, 10, "bold"))
    style.configure("TLabelframe.Label", font=common.ui_font(ui_font_family, 10, "bold"))
    style.configure("Card.TLabelframe", background=frame_bg)
    style.configure(
        "Card.TLabelframe.Label",
        background=frame_bg,
        foreground=label_fg,
        font=common.ui_font(ui_font_family, 10, "bold"),
    )
    style.configure("Inset.TLabelframe", background=frame_bg)
    style.configure(
        "Inset.TLabelframe.Label",
        background=frame_bg,
        foreground=label_fg,
        font=common.ui_font(ui_font_family, 10, "bold"),
    )
    style.configure("TButton", font=common.ui_font(ui_font_family, 15, "bold"), padding=(14, 6))
    style.configure("Action.TButton", font=common.ui_font(ui_font_family, 15, "bold"), padding=(14, 6))
    return frame_bg
