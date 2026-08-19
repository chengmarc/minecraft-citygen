"""ttkbootstrap theme helpers for the CityGen GUI."""

from __future__ import annotations

import ttkbootstrap as ttk

from gui import common


def configure_app_style(app, ui_font_family: str) -> str:
    style = app.style if hasattr(app, "style") else ttk.Style(theme=common.GUI_THEME)
    style.use_dynamic_foreground(True)
    _apply_palette(style)
    _configure_widget_styles(style, ui_font_family)
    app.configure(background=common.theme.APP_BG)
    return common.theme.APP_BG


def _apply_palette(style) -> None:
    colors = style.colors
    surface = common.blend(colors.bg, colors.primary, 0.08)
    tooltip_bg = common.blend(colors.dark, colors.bg, 0.12)
    tick = common.blend(colors.border, colors.bg, 0.32)
    common.theme.apply(
        app_bg=colors.bg,
        border=colors.border,
        text=colors.fg,
        accent=colors.primary,
        canvas_bg=surface,
        canvas_text=colors.fg,
        tick=tick,
        tooltip_bg=tooltip_bg,
        tooltip_text=colors.selectfg,
    )


def _configure_widget_styles(style, ui_font_family: str) -> None:
    base_font = common.ui_font(ui_font_family, 10)
    emphasis_font = common.ui_font(ui_font_family, 12, "bold")
    title_font = common.ui_font(ui_font_family, 11, "bold")

    style.configure(".", font=base_font)
    style.configure("TButton", font=emphasis_font, padding=(12, 8))
    style.configure("TNotebook", tabmargins=(0, 8, 0, 0))
    style.configure("TNotebook.Tab", font=emphasis_font, padding=(18, 10))
    style.configure("TLabelframe", padding=14)
    style.configure("TLabelframe.Label", font=title_font)
    style.configure("TProgressbar", thickness=10)
    style.configure("TEntry", padding=6)
    style.configure("TCombobox", padding=6)
