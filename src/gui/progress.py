"""Weighted progress-bar behavior shared by the preview and render tabs."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk

from gui import common


class WeightedProgressMixin:
    def _init_weighted_progress(self):
        self._progress_after_id = None
        self._progress_soft_target = 0.0

    def _build_progress_bar(self, row):
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(self, mode="determinate", variable=self.progress_var, bootstyle="primary")
        self.progress_bar.grid(row=row, column=0, sticky="ew", pady=(6, 0))

    def _start_progress(self):
        self._cancel_progress_animation()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", maximum=100)
        self.progress_var.set(0)
        self._progress_soft_target = 0.0

    def _finish_progress(self):
        self._cancel_progress_animation()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_var.set(self.progress_bar.cget("maximum"))

    def _stop_progress(self):
        self._cancel_progress_animation()
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")

    def _begin_script_progress(self, start_value, end_value, status):
        self._cancel_progress_animation()
        self.progress_var.set(start_value)
        segment = max(float(end_value) - float(start_value), 0.0)
        self._progress_soft_target = float(start_value) + segment * common.SCRIPT_PROGRESS_HEADROOM
        self.set_status(status)
        self._schedule_progress_tick()

    def _complete_script_progress(self, value):
        self._cancel_progress_animation()
        self.progress_var.set(value)

    def _schedule_progress_tick(self):
        self._progress_after_id = self.after(common.SCRIPT_PROGRESS_TICK_MS, self._progress_tick)

    def _progress_tick(self):
        self._progress_after_id = None
        current = float(self.progress_var.get())
        if current >= self._progress_soft_target:
            return
        remaining = self._progress_soft_target - current
        step = max(0.2, remaining * 0.07)
        self.progress_var.set(min(current + step, self._progress_soft_target))
        if float(self.progress_var.get()) < self._progress_soft_target:
            self._schedule_progress_tick()

    def _cancel_progress_animation(self):
        if self._progress_after_id is not None:
            self.after_cancel(self._progress_after_id)
            self._progress_after_id = None
