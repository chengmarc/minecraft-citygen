"""Render tab UI."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk

from config.config_algo import DEFAULT_SEED
from config.config_path import CITY_PROD_SCHEM
from pipeline import services

from gui import common
from gui.jobs import run_weighted_tasks_async
from gui.widgets import ImageViewer, WeightedProgressMixin, build_shared_config_frame


class CityTab(WeightedProgressMixin, ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=8)
        self._init_weighted_progress()
        self._suspend_auto_save = False
        saved_config = self.winfo_toplevel().get_saved_config_section("render") or common.default_algo_tab_config()

        self.city_viewer = ImageViewer(
            self,
            "City Schematic Render",
            initial_message="Click Render to construct and render the city schematic.",
            show_title=False,
        )
        self.city_viewer.grid(row=0, column=0, sticky="nsew")

        self.config_frame = ttk.Frame(self, padding=12)
        self.config_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.seed_var = tk.StringVar(value=str(saved_config.get("seed", DEFAULT_SEED)))
        self.config_vars = common.create_config_vars(saved_config.get("algo"))
        self.render_button = build_shared_config_frame(
            self.config_frame,
            self.seed_var,
            self.config_vars,
            "Render",
            self._run_render,
            "city_config",
            extra_actions=[("Output", self._open_output_folder)],
        )
        self._bind_auto_save()
        self.status_var = tk.StringVar(value="")
        self.status_label = ttk.Label(self, textvariable=self.status_var, anchor="w")
        self.status_label.grid(row=2, column=0, sticky="ew", pady=(2, 0))
        self.status_label.grid_remove()
        self._build_progress_bar(3)
        self.progress_bar.grid_configure(pady=(2, 0))

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def set_status(self, status):
        self.status_var.set(status)
        if status:
            self.status_label.grid()
        else:
            self.status_label.grid_remove()

    def _current_config_state(self):
        return {
            "seed": self.seed_var.get().strip(),
            "algo": common.snapshot_config_vars(self.config_vars),
        }

    def _bind_auto_save(self):
        self.seed_var.trace_add("write", self._on_config_changed)
        for variable in self.config_vars.values():
            variable.trace_add("write", self._on_config_changed)

    def _on_config_changed(self, *_args):
        if self._suspend_auto_save:
            return
        self.winfo_toplevel().set_saved_config_section("render", self._current_config_state())

    def _open_output_folder(self):
        if not os.path.isdir(CITY_PROD_SCHEM):
            messagebox.showerror("Output folder missing", CITY_PROD_SCHEM)
            return
        try:
            common.open_in_file_manager(CITY_PROD_SCHEM)
        except OSError as exc:
            messagebox.showerror("Could not open output folder", str(exc))

    def _run_render(self):
        seed = self.seed_var.get().strip()
        try:
            common.validate_seed(seed)
            env = common.build_algo_env(self.config_vars)
            fine = env["MC_CITY_FINE"]
        except ValueError as exc:
            title = "Invalid seed" if str(exc) == "Seed must be an integer." else "Invalid city config"
            messagebox.showerror(title, str(exc))
            return

        tasks = [
            (services.CITY_CONSTRUCT, common.RENDER_PROGRESS_WEIGHTS[0][1], lambda: services.run_city_construct_stage(seed, fine, env_overrides=env)),
            (services.CITY_RENDER, common.RENDER_PROGRESS_WEIGHTS[1][1], lambda: services.run_city_render_stage(env_overrides=env)),
        ]
        run_weighted_tasks_async(
            self,
            self.render_button,
            tasks,
            "Starting render...",
            "Render failed",
            "Render failed",
            "Render complete",
            lambda: self.city_viewer.load_image(common.city_render_path(seed)),
        )
