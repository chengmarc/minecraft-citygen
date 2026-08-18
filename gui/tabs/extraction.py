"""Extraction tab UI."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from config.config_world import BUILD_TYPES, ROAD_BOX, SAVE
from pipeline import services

from gui import common
from gui.widgets import ExtractionSubPanel, ImageViewer


class ExtractionTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10, style="Page.TFrame")

        top = ttk.Frame(self, style="Page.TFrame")
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
        self.road_viewer.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        self.build_viewer = ImageViewer(
            top,
            title="Extracted Build Assets",
            min_height=420,
            initial_message="Click Extract to scan build assets and render the contact sheet.",
        )
        self.build_viewer.image_path = common.BUILD_CONTACT_SHEET
        self.build_viewer.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        self.config_frame = ttk.LabelFrame(self, text="Extraction Config", padding=8, style="Card.TLabelframe")
        self.config_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.config_frame.columnconfigure(1, weight=1)

        self.world_var = tk.StringVar(value=SAVE)
        ttk.Label(self.config_frame, text="World Location").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(self.config_frame, textvariable=self.world_var).grid(row=0, column=1, sticky="ew")

        subpanels = ttk.Frame(self.config_frame, style="Card.TFrame")
        subpanels.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        subpanels.columnconfigure(0, weight=1, uniform="extract_config")
        subpanels.columnconfigure(1, weight=1, uniform="extract_config")

        self.road_config = ExtractionSubPanel(subpanels, "Road Assets Region", "road", ROAD_BOX)
        self.road_config.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self.road_config.set_extract_command(
            lambda: self._run_extract("road", self.road_config, self.road_viewer, "MC_CITY_ROAD_BOX")
        )

        self.build_config = ExtractionSubPanel(subpanels, "Build Assets Region", "build", BUILD_TYPES)
        self.build_config.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self.build_config.set_extract_command(
            lambda: self._run_extract("build", self.build_config, self.build_viewer, "MC_CITY_BUILD_TYPES")
        )

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(self, mode="determinate", variable=self.progress_var)
        self.progress_bar.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        self.rowconfigure(2, weight=0)
        self.rowconfigure(0, weight=1)

    def set_status(self, status):
        self.config_frame.configure(text=f"Extraction Config - {status}")

    def _run_extract(self, kind, config, viewer, area_env_key):
        env = {"MC_CITY_SAVE": self.world_var.get().strip()}
        try:
            env[area_env_key] = config.area_env_value()
        except ValueError as exc:
            messagebox.showerror("Invalid extraction area", str(exc))
            return

        def worker():
            self.after(0, lambda: config.extract_button.configure(state="disabled"))
            self.after(0, lambda: self.set_status(f"Preparing {kind} extract..."))

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

                if kind == "road":
                    services.run_road_extraction_pipeline(env_overrides=env, progress=on_progress)
                else:
                    services.run_build_extraction_pipeline(env_overrides=env, progress=on_progress)
            except Exception as exc:
                message = str(exc).strip()
                self.after(0, self._stop_progress)
                self.after(0, lambda: self.set_status("Extract failed"))
                self.after(0, lambda: messagebox.showerror("Extract failed", message))
            else:
                self.after(0, lambda: viewer.load_image(viewer.image_path))
                self.after(0, self._finish_progress)
                self.after(0, lambda: self.set_status("Extract complete"))
            finally:
                self.after(0, lambda: config.extract_button.configure(state="normal"))

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
