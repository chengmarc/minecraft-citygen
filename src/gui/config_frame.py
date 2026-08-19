"""Builders for the shared seed/config frame on the preview and render tabs."""

from __future__ import annotations

import ttkbootstrap as ttk

from gui import common
from gui.controls import ActionButton, IntegerSlider
from gui.tooltip import Tooltip


def create_config_input(master, text_var, name):
    if name in common.PREVIEW_SLIDER_RANGES:
        lo, hi = common.PREVIEW_SLIDER_RANGES[name]
        return IntegerSlider(master, text_var, lo, hi)
    return ttk.Entry(master, textvariable=text_var, width=13)


def build_shared_config_frame(
    config_frame,
    seed_var,
    config_vars,
    action_text,
    action_command,
    uniform_name,
    extra_actions=None,
):
    config_frame.columnconfigure(6, weight=1)

    ttk.Label(config_frame, text="Seed").grid(row=0, column=0, sticky="w", padx=(0, 6))
    ttk.Entry(config_frame, textvariable=seed_var, width=14).grid(row=0, column=1, sticky="w")

    city_size_label = ttk.Label(config_frame, text="City Size")
    city_size_label.grid(row=0, column=2, sticky="w", padx=(8, 6))
    Tooltip(city_size_label, common.PREVIEW_CONFIG_LOOKUP["FINE"][1])
    city_size_input = ttk.Combobox(
        config_frame,
        textvariable=config_vars["FINE"],
        values=list(common.CANVAS_SIZE_OPTIONS),
        state="readonly",
        width=12,
    )
    city_size_input.grid(row=0, column=3, sticky="w")
    Tooltip(city_size_input, common.PREVIEW_CONFIG_LOOKUP["FINE"][1])

    density_label = ttk.Label(config_frame, text="Grid Density")
    density_label.grid(row=0, column=4, sticky="w", padx=(8, 6))
    Tooltip(density_label, common.PREVIEW_CONFIG_LOOKUP["GAP_MIXED"][1])
    density_input = ttk.Combobox(
        config_frame,
        textvariable=config_vars["GAP_MIXED"],
        values=list(common.CLEARANCE_OPTIONS),
        state="readonly",
        width=13,
    )
    density_input.grid(row=0, column=5, sticky="w")
    Tooltip(density_input, common.PREVIEW_CONFIG_LOOKUP["GAP_MIXED"][1])

    actions_frame = ttk.Frame(config_frame)
    actions_frame.grid(row=0, column=7, sticky="e")

    if extra_actions:
        for column, (text, command) in enumerate(extra_actions):
            icon_name = None
            if text in {"Output", "Output Folder"}:
                icon_name = "folder"
            extra_button = ActionButton(
                actions_frame,
                text=text,
                icon_name=icon_name,
                command=command,
                width=max(common.BUTTON_WIDTH, len(text) + 1),
            )
            extra_button.grid(row=0, column=column, sticky="e", padx=(0, 6))

    action_column = len(extra_actions or [])
    icon_name = None
    if action_text == "Preview":
        icon_name = "preview"
    elif action_text == "Render":
        icon_name = "render"
    action_button = ActionButton(
        actions_frame,
        text=action_text,
        icon_name=icon_name,
        command=action_command,
        width=common.BUTTON_WIDTH + 3,
    )
    action_button.grid(row=0, column=action_column, sticky="e")

    config_grid = ttk.Frame(config_frame)
    config_grid.grid(row=1, column=0, columnspan=8, sticky="ew", pady=(10, 0))
    for column in range(len(common.PREVIEW_CONFIG_GROUPS)):
        config_grid.columnconfigure(column, weight=1, uniform=uniform_name)

    for group_col, (group_title, names) in enumerate(common.PREVIEW_CONFIG_GROUPS):
        group = ttk.LabelFrame(config_grid, text=group_title)
        group.grid(row=0, column=group_col, sticky="nsew", padx=(0 if group_col == 0 else 4, 0))
        group.columnconfigure(1, weight=1)
        for row, name in enumerate(names):
            label, description = common.PREVIEW_CONFIG_LOOKUP[name]
            label_widget = ttk.Label(group, text=label)
            label_widget.grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
            Tooltip(label_widget, description)
            input_widget = create_config_input(group, config_vars[name], name)
            input_widget.grid(row=row, column=1, sticky="ew", pady=2)
            Tooltip(input_widget, description)

    return action_button
