"""Button and slider controls used across the GUI."""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk

from gui import common


def _action_bootstyle(label, icon_name):
    if label in {"Preview", "Render", "Extract", "Use Selection"}:
        return "primary"
    if label in {"Cancel", "Pick", "Output", "Output Folder"}:
        return "secondary"
    if icon_name in {"preview", "render", "extract"}:
        return "primary"
    if icon_name == "folder":
        return "secondary"
    return "secondary"


class ActionButton(ttk.Frame):
    def __init__(self, master, icon_name=None, icon_size=24, **button_kwargs):
        super().__init__(master)
        self._icon = None
        if icon_name and "image" not in button_kwargs:
            self._icon = common.load_icon(icon_name, size=icon_size)
            if self._icon is not None:
                button_kwargs.setdefault("image", self._icon)
                button_kwargs.setdefault("compound", "left")
        button_kwargs.setdefault("bootstyle", _action_bootstyle(button_kwargs.get("text"), icon_name))
        self.button = ttk.Button(self, **button_kwargs)
        self.button.grid(row=0, column=0, sticky="nsew")

    def configure(self, cnf=None, **kwargs):
        return self.button.configure(cnf, **kwargs)

    config = configure

    def cget(self, key):
        return self.button.cget(key)

    def state(self, states=None):
        return self.button.state(states)

    def invoke(self):
        return self.button.invoke()


class IntegerSlider(ttk.Frame):
    def __init__(self, master, text_var, minimum, maximum):
        super().__init__(master)
        self.text_var = text_var
        self.minimum = minimum
        self.maximum = maximum
        self.value_var = tk.IntVar(value=self._coerce(text_var.get()))
        self._tick_after_id = None
        self._last_tick_width = None
        tick_bg = common.theme.APP_BG

        self.scale = ttk.Scale(
            self,
            from_=minimum,
            to=maximum,
            orient="horizontal",
            command=self._on_slide,
            bootstyle="primary",
        )
        self.scale.set(self.value_var.get())
        self.scale.grid(row=0, column=0, sticky="ew")
        ttk.Label(self, textvariable=self.value_var, width=3, anchor="e").grid(row=0, column=1, sticky="e", padx=(6, 0))
        self.ticks = tk.Canvas(self, height=10, highlightthickness=0, bg=tick_bg, bd=0)
        self.ticks.grid(row=1, column=0, sticky="ew", pady=(1, 0))
        self.ticks.bind("<Configure>", self._schedule_draw_ticks)
        self.columnconfigure(0, weight=1)
        text_var.trace_add("write", self._on_text_change)

    def _coerce(self, value):
        try:
            parsed = int(float(value))
        except ValueError:
            parsed = self.minimum
        return min(max(parsed, self.minimum), self.maximum)

    def _on_slide(self, value):
        parsed = self._coerce(value)
        self.value_var.set(parsed)
        if abs(self.scale.get() - parsed) > 0.001:
            self.scale.set(parsed)
        if self.text_var.get() != str(parsed):
            self.text_var.set(str(parsed))

    def _on_text_change(self, *_args):
        parsed = self._coerce(self.text_var.get())
        if self.value_var.get() != parsed:
            self.value_var.set(parsed)
            self.scale.set(parsed)

    def _schedule_draw_ticks(self, _event=None):
        if self._tick_after_id is not None:
            self.after_cancel(self._tick_after_id)
        self._tick_after_id = self.after(16, self._draw_ticks)

    def _draw_ticks(self):
        self._tick_after_id = None
        self.ticks.delete("all")
        width = self.ticks.winfo_width()
        if width <= 1:
            self._last_tick_width = None
            return
        if self._last_tick_width == width:
            return
        self._last_tick_width = width
        inset = max(8, int(9 * float(self.tk.call("tk", "scaling"))))
        span = max(width - inset * 2, 1)
        steps = max(self.maximum - self.minimum, 1)
        for index in range(steps + 1):
            x = inset + span * index / steps
            self.ticks.create_line(x, 1, x, 8, fill=common.theme.TICK)
