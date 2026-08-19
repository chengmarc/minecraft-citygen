"""Extraction tab UI."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from config.config_world import BUILD_TYPES, ROAD_BOX, SAVE
from pipeline import services

from gui import common
from gui.widgets import ActionButton, ExtractionSubPanel, ImageViewer, RegionSelectorDialog


class ExtractionTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self._suspend_auto_save = False
        saved_config = self.winfo_toplevel().get_saved_config_section("extraction") or common.default_extraction_tab_config()

        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="nsew")
        top.columnconfigure(0, weight=1, uniform="extract_view")
        top.columnconfigure(1, weight=1, uniform="extract_view")
        top.rowconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.road_viewer = ImageViewer(
            top,
            title="Extracted Road Assets",
            min_height=420,
            initial_message="Click Extract to scan road assets and render the contact sheet.",
        )
        self.road_viewer.image_path = common.ROAD_CONTACT_SHEET
        self.road_viewer.grid(row=0, column=0, sticky="nsew")

        self.build_viewer = ImageViewer(
            top,
            title="Extracted Build Assets",
            min_height=420,
            initial_message="Click Extract to scan build assets and render the contact sheet.",
        )
        self.build_viewer.image_path = common.BUILD_CONTACT_SHEET
        self.build_viewer.grid(row=0, column=1, sticky="nsew")

        self.config_frame = ttk.LabelFrame(self, text="Extraction")
        self.config_frame.grid(row=1, column=0, sticky="ew")
        self.config_frame.columnconfigure(0, weight=1)

        self.world_var = tk.StringVar(value=SAVE)
        header_row = ttk.Frame(self.config_frame)
        header_row.grid(row=0, column=0, sticky="ew")
        header_row.columnconfigure(2, weight=1)
        ttk.Label(header_row, text="World Location").grid(row=0, column=0, sticky="w")
        ttk.Entry(header_row, textvariable=self.world_var, width=48).grid(row=0, column=1, sticky="w")
        header_actions = ttk.Frame(header_row)
        header_actions.grid(row=0, column=3, sticky="e")
        self.extract_button = ActionButton(
            header_actions,
            text="Extract",
            icon_name="extract",
            width=common.BUTTON_WIDTH + 4,
        )
        self.extract_button.grid(row=0, column=0)

        subpanels = ttk.Frame(self.config_frame)
        subpanels.grid(row=1, column=0, sticky="ew")
        subpanels.columnconfigure(0, weight=1, uniform="extract_config")
        subpanels.columnconfigure(1, weight=1, uniform="extract_config")
        subpanels.columnconfigure(2, weight=1, uniform="extract_config")

        self.road_config = ExtractionSubPanel(subpanels, "Road Assets Region", "road", ROAD_BOX, show_extract_button=False)
        self.road_config.grid(row=0, column=0, sticky="nsew")
        self.road_config.set_pick_command(
            "road",
            lambda: self._open_region_selector(self.road_config, "road", "Road Region Selector"),
        )

        self.house_config = ExtractionSubPanel(subpanels, "House Assets Region", "house", BUILD_TYPES, show_extract_button=False)
        self.house_config.grid(row=0, column=1, sticky="nsew")
        self.house_config.set_pick_command(
            "house",
            lambda: self._open_region_selector(self.house_config, "house", "House Region Selector"),
        )

        self.landmark_config = ExtractionSubPanel(subpanels, "Landmark Assets Region", "landmark", BUILD_TYPES, show_extract_button=False)
        self.landmark_config.grid(row=0, column=2, sticky="nsew")
        self.landmark_config.set_pick_command(
            "landmark",
            lambda: self._open_region_selector(self.landmark_config, "landmark", "Landmark Region Selector"),
        )
        self.extract_button.configure(command=self._run_extract_all)
        self._apply_config_state(saved_config)
        self._bind_auto_save()

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(self, mode="determinate", variable=self.progress_var)
        self.progress_bar.grid(row=2, column=0, sticky="ew")

        self.rowconfigure(2, weight=0)
        self.rowconfigure(0, weight=1)

    def set_status(self, status):
        self.config_frame.configure(text=f"Extraction - {status}")

    def _current_config_state(self):
        return {
            "world_path": self.world_var.get().strip(),
            "road": self._serialize_panel_state(self.road_config, "road"),
            "house": self._serialize_panel_state(self.house_config, "house"),
            "landmark": self._serialize_panel_state(self.landmark_config, "landmark"),
        }

    def _bind_auto_save(self):
        self.world_var.trace_add("write", self._on_config_changed)
        for panel, key in (
            (self.road_config, "road"),
            (self.house_config, "house"),
            (self.landmark_config, "landmark"),
        ):
            start_key, end_key = {
                "road": ("road_start", "road_end"),
                "house": ("house_start", "house_end"),
                "landmark": ("landmark_start", "landmark_end"),
            }[key]
            panel.area_vars[start_key].trace_add("write", self._on_config_changed)
            panel.area_vars[end_key].trace_add("write", self._on_config_changed)

    def _on_config_changed(self, *_args):
        if self._suspend_auto_save:
            return
        self.winfo_toplevel().set_saved_config_section("extraction", self._current_config_state())

    def _serialize_panel_state(self, panel, key):
        start, end = panel.get_xyz_pair(key)
        return {
            "start": list(start),
            "end": list(end),
        }

    def _coerce_xyz_triplet(self, value):
        return tuple(int(part) for part in value)

    def _apply_config_state(self, config):
        if not config:
            return
        self._suspend_auto_save = True
        try:
            self.world_var.set(str(config.get("world_path", SAVE)))
            for key, panel in (
                ("road", self.road_config),
                ("house", self.house_config),
                ("landmark", self.landmark_config),
            ):
                region = config.get(key)
                if not isinstance(region, dict):
                    continue
                start = region.get("start")
                end = region.get("end")
                if start is None or end is None:
                    continue
                panel.set_xyz_pair(key, self._coerce_xyz_triplet(start), self._coerce_xyz_triplet(end))
        finally:
            self._suspend_auto_save = False

    def _open_region_selector(self, panel, key, title):
        start, end = panel.get_xyz_pair(key)
        save_path = self.world_var.get().strip()
        if not save_path:
            messagebox.showerror("Missing world path", "World Location must be set before opening the region selector.")
            return

        RegionSelectorDialog(
            self,
            title=title,
            save_path=save_path,
            start_xyz=start,
            end_xyz=end,
            on_apply=lambda new_start, new_end: panel.set_xyz_pair(key, new_start, new_end),
        )

    def _run_extract_all(self):
        env = {"MC_CITY_SAVE": self.world_var.get().strip()}
        env["MC_CITY_ROAD_BOX"] = self.road_config.area_env_value()
        env["MC_CITY_BUILD_TYPES"] = ";".join(
            [
                self.house_config.area_env_value(),
                self.landmark_config.area_env_value(),
            ]
        )

        def worker():
            self.after(0, lambda: self.extract_button.configure(state="disabled"))
            self.after(0, lambda: self.set_status("Preparing extract..."))

            try:
                current_stage = {"name": None}

                def on_progress(stage, completed, total, _label):
                    def update():
                        if current_stage["name"] != stage:
                            current_stage["name"] = stage
                            self._start_determinate(total)
                        self.progress_var.set(completed)
                        self.set_status(f"{stage} {completed}/{total}")

                    self.after(0, update)

                services.run_road_extraction_pipeline(env_overrides=env, progress=on_progress)
                services.run_build_extraction_pipeline(env_overrides=env, progress=on_progress)
            except Exception as exc:
                message = str(exc).strip()
                self.after(0, self._stop_progress)
                self.after(0, lambda: self.set_status("Extract failed"))
                self.after(0, lambda: messagebox.showerror("Extract failed", message))
            else:
                self.after(0, lambda: self.road_viewer.load_image(self.road_viewer.image_path))
                self.after(0, lambda: self.build_viewer.load_image(self.build_viewer.image_path))
                self.after(0, self._finish_progress)
                self.after(0, lambda: self.set_status("Extract complete"))
            finally:
                self.after(0, lambda: self.extract_button.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _start_determinate(self, total):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", maximum=max(total, 1))
        self.progress_var.set(0)

    def _finish_progress(self):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_var.set(self.progress_bar.cget("maximum"))

    def _stop_progress(self):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
