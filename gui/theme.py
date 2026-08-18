"""Theme helpers for the Tk application shell."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui import common


def configure_app_style(app: tk.Misc, ui_font_family: str) -> str:
    style = ttk.Style(app)
    style.theme_use(common.GUI_THEME)

    frame_bg = common.resolve_color(app, style.lookup("TFrame", "background"), "#f3f6fb")
    label_fg = style.lookup("TLabel", "foreground") or common.TEXT

    style.configure(".", font=common.ui_font(ui_font_family, 10), foreground=label_fg)
    style.configure("Page.TFrame", background=frame_bg)
    style.configure("Card.TFrame", background=frame_bg)
    style.configure("TLabel", background=frame_bg, foreground=label_fg)
    style.configure("App.TNotebook", background=frame_bg, borderwidth=0)
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
    style.configure("TButton", font=common.ui_font(ui_font_family, 20, "bold"), padding=(12, 6), borderwidth=0, relief="flat")
    style.configure("Action.TButton", font=common.ui_font(ui_font_family, 20, "bold"), padding=(12, 6), borderwidth=0, relief="flat")

    _apply_rounded_theme(app, style, frame_bg, label_fg)
    return frame_bg


def _photo_asset(app: tk.Misc, key: str, width: int, height: int, radius: int, fill: str, outline: str | None = None, outline_width: int = 1):
    image = common.ImageTk.PhotoImage(
        common.rounded_image(width, height, radius, fill, outline=outline, outline_width=outline_width)
    )
    app._theme_images[key] = image
    return image


def _replace_style_element(style: ttk.Style, style_name: str, source: str, target: str) -> None:
    try:
        current = style.layout(style_name)
        style.layout(style_name, common.replace_layout_element(current, source, target))
    except tk.TclError:
        return


def _create_image_element(style: ttk.Style, name: str, default, *states, border: int = 8, sticky: str = "nsew") -> None:
    try:
        style.element_create(name, "image", default, *states, border=border, sticky=sticky)
    except tk.TclError:
        return


def _apply_rounded_theme(app: tk.Misc, style: ttk.Style, frame_bg: str, label_fg: str) -> None:
    if common.Image is None or common.ImageDraw is None or common.ImageTk is None:
        return

    app._theme_images = {}
    surface = common.blend(frame_bg, "#ffffff", 0.78)
    outline = common.blend(frame_bg, common.BORDER, 0.80)
    panel_outline = common.blend(frame_bg, "#2b3444", 0.82)
    subtle_outline = common.blend(outline, "#ffffff", 0.18)
    accent_active = common.blend(common.ACCENT, "#ffffff", 0.14)
    accent_pressed = common.blend(common.ACCENT, "#000000", 0.12)
    disabled_fill = common.blend(surface, frame_bg, 0.35)
    disabled_outline = common.blend(outline, frame_bg, 0.35)
    slider_fill = common.blend(common.ACCENT, "#ffffff", 0.05)

    button_normal = _photo_asset(app, "button_normal", 28, 28, common.UI_RADIUS + 2, common.ACCENT, outline=common.ACCENT)
    button_active = _photo_asset(app, "button_active", 28, 28, common.UI_RADIUS + 2, accent_active, outline=accent_active)
    button_pressed = _photo_asset(app, "button_pressed", 28, 28, common.UI_RADIUS + 2, accent_pressed, outline=accent_pressed)
    button_disabled = _photo_asset(app, "button_disabled", 28, 28, common.UI_RADIUS + 2, disabled_fill, outline=disabled_outline)
    field_normal = _photo_asset(app, "field_normal", 28, 28, common.UI_RADIUS + 2, "#ffffff", outline=outline)
    field_focus = _photo_asset(app, "field_focus", 28, 28, common.UI_RADIUS + 2, "#ffffff", outline=common.ACCENT)
    field_disabled = _photo_asset(app, "field_disabled", 28, 28, common.UI_RADIUS + 2, disabled_fill, outline=disabled_outline)
    tab_normal = _photo_asset(app, "tab_normal", 30, 24, common.UI_RADIUS + 2, surface, outline=subtle_outline)
    tab_selected = _photo_asset(app, "tab_selected", 30, 24, common.UI_RADIUS + 2, "#ffffff", outline=common.ACCENT)
    group_border = _photo_asset(app, "group_border", 28, 28, common.UI_RADIUS + 2, frame_bg, outline=panel_outline, outline_width=2)
    progress_trough = _photo_asset(app, "progress_trough", 28, 14, common.UI_RADIUS + 3, surface, outline=subtle_outline)
    progress_bar = _photo_asset(app, "progress_bar", 28, 14, common.UI_RADIUS + 3, common.ACCENT, outline=common.ACCENT)
    scale_trough = _photo_asset(app, "scale_trough", 28, 10, common.UI_RADIUS + 1, surface, outline=subtle_outline)
    scale_slider = _photo_asset(app, "scale_slider", 18, 18, 9, slider_fill, outline=common.ACCENT)

    _create_image_element(style, "Rounded.Button.border", button_normal, ("disabled", button_disabled), ("pressed", button_pressed), ("active", button_active))
    _create_image_element(style, "Rounded.Entry.field", field_normal, ("disabled", field_disabled), ("focus", field_focus), ("invalid", field_focus))
    _create_image_element(style, "Rounded.Combobox.field", field_normal, ("readonly", field_normal), ("disabled", field_disabled), ("focus", field_focus))
    _create_image_element(style, "Rounded.Notebook.tab", tab_normal, ("selected", tab_selected), ("active", tab_selected))
    _create_image_element(style, "Rounded.Labelframe.border", group_border)
    _create_image_element(style, "Rounded.Progressbar.trough", progress_trough, border=7)
    _create_image_element(style, "Rounded.Progressbar.pbar", progress_bar, border=7)
    _create_image_element(style, "Rounded.Scale.trough", scale_trough, border=5)
    _create_image_element(style, "Rounded.Scale.slider", scale_slider, ("pressed", button_pressed), ("active", button_active), border=9)

    _replace_style_element(style, "TButton", "Button.border", "Rounded.Button.border")
    _replace_style_element(style, "TEntry", "Entry.field", "Rounded.Entry.field")
    _replace_style_element(style, "TCombobox", "Combobox.field", "Rounded.Combobox.field")
    _replace_style_element(style, "TNotebook.Tab", "Notebook.tab", "Rounded.Notebook.tab")
    _replace_style_element(style, "TLabelframe", "Labelframe.border", "Rounded.Labelframe.border")
    _replace_style_element(style, "Horizontal.TProgressbar", "Horizontal.Progressbar.trough", "Rounded.Progressbar.trough")
    _replace_style_element(style, "Horizontal.TProgressbar", "Horizontal.Progressbar.pbar", "Rounded.Progressbar.pbar")
    _replace_style_element(style, "Horizontal.TScale", "Horizontal.Scale.trough", "Rounded.Scale.trough")
    _replace_style_element(style, "Horizontal.TScale", "Horizontal.Scale.slider", "Rounded.Scale.slider")

    style.configure("TEntry", padding=(10, 6), fieldbackground="#ffffff", borderwidth=0, relief="flat")
    style.configure("TCombobox", padding=(10, 6), fieldbackground="#ffffff", borderwidth=0, relief="flat", arrowsize=12)
    style.configure("TNotebook.Tab", padding=(14, 8))
    style.configure("Horizontal.TProgressbar", thickness=14, borderwidth=0)
    style.configure("Horizontal.TScale", sliderthickness=18, troughcolor=surface)
    style.map("TNotebook.Tab", foreground=[("selected", label_fg), ("active", label_fg)])
    style.map("TCombobox", fieldbackground=[("readonly", "#ffffff"), ("focus", "#ffffff")], background=[("readonly", "#ffffff")])
