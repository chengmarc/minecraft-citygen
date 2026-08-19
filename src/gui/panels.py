"""Extraction-tab region sub-panel."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk

from gui import common
from gui.controls import ActionButton


def _format_extraction_xyz(pos):
    return f"({common.format_xyz(pos)})"


class ExtractionSubPanel(ttk.LabelFrame):
    def __init__(self, master, title, area_kind, area_value, show_extract_button=True):
        super().__init__(master, text=title)
        self.area_kind = area_kind
        self.area_vars = {}
        self.pick_buttons = {}
        self.extract_button = None
        self.content = ttk.Frame(self)

        self.rowconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)
        self.content.grid(row=1, column=0, sticky="ew")

        self._build_area(area_value)
        if show_extract_button:
            self.extract_button = ActionButton(
                self.content,
                text="Extract",
                icon_name="extract",
                width=common.BUTTON_WIDTH + 2,
            )
            self.extract_button.grid(row=0, column=5, padx=(4, 0))

        self.content.columnconfigure(1, weight=1)
        self.content.columnconfigure(3, weight=1)

    def _build_xyz_row(self, row, start_key, end_key, start_value, end_value, picker_key):
        self.area_vars[start_key] = tk.StringVar(value=_format_extraction_xyz(start_value))
        self.area_vars[end_key] = tk.StringVar(value=_format_extraction_xyz(end_value))
        ttk.Label(self.content, text="From").grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(self.content, textvariable=self.area_vars[start_key], state="readonly").grid(
            row=row,
            column=1,
            sticky="ew",
            padx=(0, 6),
            pady=2,
        )
        ttk.Label(self.content, text="To").grid(row=row, column=2, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(self.content, textvariable=self.area_vars[end_key], state="readonly").grid(
            row=row,
            column=3,
            sticky="ew",
            padx=(0, 6),
            pady=2,
        )
        pick_button = ActionButton(self.content, text="Pick", width=common.BUTTON_WIDTH)
        pick_button.grid(row=row, column=4, sticky="e", padx=(4, 0))
        self.pick_buttons[picker_key] = pick_button

    def _build_area(self, area_value):
        if self.area_kind == "road":
            start, end = common.region_to_xyz_pair(area_value)
            self._build_xyz_row(0, "road_start", "road_end", start, end, "road")
            return

        build_type = 1 if self.area_kind == "house" else 2
        region = common.first_build_region(area_value, build_type)
        start, end = common.region_to_xyz_pair(region)
        self._build_xyz_row(0, f"{self.area_kind}_start", f"{self.area_kind}_end", start, end, self.area_kind)

    def area_env_value(self):
        if self.area_kind == "road":
            start = common.parse_xyz(self.area_vars["road_start"].get(), "Road cube start")
            end = common.parse_xyz(self.area_vars["road_end"].get(), "Road cube end")
            return common.BlockRegion.from_xyz_pair(start, end).to_env_value()

        start = common.parse_xyz(self.area_vars[f"{self.area_kind}_start"].get(), f"{self.area_kind.title()} cube start")
        end = common.parse_xyz(self.area_vars[f"{self.area_kind}_end"].get(), f"{self.area_kind.title()} cube end")
        build_type = 1 if self.area_kind == "house" else 2
        return common.BuildRegion(build_type, common.BlockRegion.from_xyz_pair(start, end)).to_env_value()

    def set_extract_command(self, command):
        if self.extract_button is not None:
            self.extract_button.configure(command=command)

    def set_pick_command(self, key, command):
        self.pick_buttons[key].configure(command=command)

    def get_xyz_pair(self, key):
        start_key, end_key = {
            "road": ("road_start", "road_end"),
            "house": ("house_start", "house_end"),
            "landmark": ("landmark_start", "landmark_end"),
        }[key]
        start = common.parse_xyz(self.area_vars[start_key].get(), f"{key.title()} cube start")
        end = common.parse_xyz(self.area_vars[end_key].get(), f"{key.title()} cube end")
        return start, end

    def set_xyz_pair(self, key, start, end):
        start_key, end_key = {
            "road": ("road_start", "road_end"),
            "house": ("house_start", "house_end"),
            "landmark": ("landmark_start", "landmark_end"),
        }[key]
        self.area_vars[start_key].set(_format_extraction_xyz(start))
        self.area_vars[end_key].set(_format_extraction_xyz(end))
