"""Reusable GUI widgets and config-frame builders."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from gui import common

Image = common.Image
ImageTk = common.ImageTk


class ImageViewer(ttk.Frame):
    def __init__(self, master, title, initial_message="", min_height=420, show_title=False):
        super().__init__(master, style="Card.TFrame", padding=6)
        self.title = title
        self.image_path = None
        self._source_image = None
        self._photo = None
        self._zoom = 1.0
        self._image_id = None
        self._message_id = None
        self._has_title = bool(title and show_title)
        self._layout_after_id = None

        canvas_row = 1 if self._has_title else 0
        if self._has_title:
            ttk.Label(self, text=title).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.canvas = tk.Canvas(
            self,
            bg=common.CANVAS_BG,
            highlightthickness=1,
            highlightbackground=common.BORDER,
            highlightcolor=common.ACCENT,
            bd=0,
            width=420,
            height=min_height,
        )
        self.canvas.grid(row=canvas_row, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(canvas_row, weight=1)

        self.canvas.bind("<Configure>", self._schedule_layout)
        self.canvas.bind("<Enter>", lambda _event: self.canvas.focus_set())
        self.canvas.bind("<MouseWheel>", self._on_zoom_wheel)
        self.canvas.bind("<Button-4>", lambda event: self._zoom_at(event.x, event.y, 1.12))
        self.canvas.bind("<Button-5>", lambda event: self._zoom_at(event.x, event.y, 1 / 1.12))
        self.canvas.bind("<ButtonPress-1>", self._start_pan)
        self.canvas.bind("<B1-Motion>", self._pan)
        self.show_message(initial_message)

    def show_message(self, message):
        self._source_image = None
        self._photo = None
        self._image_id = None
        self.canvas.delete("all")
        font_family = self.winfo_toplevel().ui_font_family
        self._message_id = self.canvas.create_text(
            20,
            20,
            anchor="nw",
            fill=common.CANVAS_TEXT,
            font=common.ui_font(font_family, 11),
            text=message,
            width=360,
        )
        self.canvas.configure(scrollregion=(0, 0, 420, 420))

    def load_image(self, image_path):
        self.image_path = image_path
        self.canvas.delete("all")
        self._image_id = None
        self._message_id = None
        if not os.path.exists(image_path):
            self.show_message(f"Image not found:\n{os.path.relpath(image_path, common.ROOT_DIR)}")
            return
        if Image is None or ImageTk is None:
            self._photo = tk.PhotoImage(file=image_path)
            self._image_id = self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
            self.canvas.configure(scrollregion=(0, 0, self._photo.width(), self._photo.height()))
            return

        self._source_image = Image.open(image_path).convert("RGBA")
        self._zoom = self._initial_zoom()
        self._render_image(center=True)

    def _schedule_layout(self, _event=None):
        if self._source_image is None or self._photo is None or self._image_id is None:
            return
        if self._layout_after_id is not None:
            self.after_cancel(self._layout_after_id)
        self._layout_after_id = self.after(60, self._apply_layout)

    def _apply_layout(self):
        self._layout_after_id = None
        if self._image_id is None or self._photo is None:
            return
        x, y = self.canvas.coords(self._image_id)
        width = self._photo.width()
        height = self._photo.height()
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if width <= canvas_width:
            x = max((canvas_width - width) // 2, 0)
        if height <= canvas_height:
            y = max((canvas_height - height) // 2, 0)
        self.canvas.coords(self._image_id, x, y)
        self._update_scrollregion()

    def _initial_zoom(self):
        if not self._source_image:
            return 1.0
        canvas_size = max(min(self.canvas.winfo_width(), self.canvas.winfo_height()), 1)
        longest_edge = max(self._source_image.width, self._source_image.height)
        return max(canvas_size / longest_edge, 0.05)

    def _render_image(self, center=False, anchor=None):
        if not self._source_image:
            return
        width = max(1, int(self._source_image.width * self._zoom))
        height = max(1, int(self._source_image.height * self._zoom))
        resample = Image.Resampling.NEAREST if self._zoom >= 1 else Image.Resampling.BILINEAR
        image = self._source_image.resize((width, height), resample)
        self._photo = ImageTk.PhotoImage(image)

        if self._image_id is None:
            self._image_id = self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            self.canvas.itemconfigure(self._image_id, image=self._photo)

        if center:
            x = max((self.canvas.winfo_width() - width) // 2, 0)
            y = max((self.canvas.winfo_height() - height) // 2, 0)
        elif anchor:
            canvas_x, canvas_y, source_x, source_y = anchor
            x = canvas_x - source_x * self._zoom
            y = canvas_y - source_y * self._zoom
        else:
            x, y = self.canvas.coords(self._image_id)

        self.canvas.coords(self._image_id, x, y)
        self._update_scrollregion()

    def _update_scrollregion(self):
        if self._image_id is None:
            return
        bbox = self.canvas.bbox(self._image_id) or (
            0,
            0,
            self._photo.width() if self._photo else 0,
            self._photo.height() if self._photo else 0,
        )
        self.canvas.configure(
            scrollregion=(
                min(0, bbox[0]),
                min(0, bbox[1]),
                max(self.canvas.winfo_width(), bbox[2]),
                max(self.canvas.winfo_height(), bbox[3]),
            )
        )

    def _on_zoom_wheel(self, event):
        factor = 1.12 if event.delta > 0 else 1 / 1.12
        self._zoom_at(event.x, event.y, factor)
        return "break"

    def _zoom_at(self, canvas_x, canvas_y, factor):
        if not self._source_image or self._image_id is None:
            return "break"
        x0, y0 = self.canvas.coords(self._image_id)
        source_x = (canvas_x - x0) / self._zoom
        source_y = (canvas_y - y0) / self._zoom
        self._zoom = min(max(self._zoom * factor, 0.05), 8.0)
        self._render_image(anchor=(canvas_x, canvas_y, source_x, source_y))
        return "break"

    def _start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def _pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)


class ActionButton(ttk.Frame):
    def __init__(self, master, **button_kwargs):
        super().__init__(master, style="Page.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.button = ttk.Button(self, style="Action.TButton", **button_kwargs)
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


class ExtractionSubPanel(ttk.LabelFrame):
    def __init__(self, master, title, area_kind, area_value):
        super().__init__(master, text="", padding=6, style="Inset.TLabelframe")
        self.area_kind = area_kind
        self.area_vars = {}
        self.content = ttk.Frame(self, style="Card.TFrame")

        self.rowconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)
        self.content.grid(row=1, column=0, sticky="ew")

        if area_kind == "road":
            self._build_road_area(area_value)
        else:
            self._build_build_area(area_value)
        button_rowspan = 1 if area_kind == "road" else 2
        self.extract_button = ActionButton(self.content, text="Extract", width=common.BUTTON_WIDTH)
        self.extract_button.grid(row=0, column=4, rowspan=button_rowspan, padx=(4, 0))

        self.content.columnconfigure(1, weight=1)
        self.content.columnconfigure(3, weight=1)

    def _build_xyz_row(self, row, label, start_key, end_key, start_value, end_value):
        self.area_vars[start_key] = tk.StringVar(value=common.format_xyz(start_value))
        self.area_vars[end_key] = tk.StringVar(value=common.format_xyz(end_value))
        ttk.Label(self.content, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(self.content, textvariable=self.area_vars[start_key]).grid(row=row, column=1, sticky="ew", padx=(0, 6), pady=2)
        ttk.Label(self.content, text="to").grid(row=row, column=2, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(self.content, textvariable=self.area_vars[end_key]).grid(row=row, column=3, sticky="ew", padx=(0, 6), pady=2)

    def _build_road_area(self, road_box):
        start, end = common.region_to_xyz_pair(road_box)
        self._build_xyz_row(0, "Road Assets", "road_start", "road_end", start, end)

    def _build_build_area(self, build_types):
        house = common.first_build_region(build_types, 1)
        landmark = common.first_build_region(build_types, 2)
        house_start, house_end = common.region_to_xyz_pair(house)
        landmark_start, landmark_end = common.region_to_xyz_pair(landmark)
        self._build_xyz_row(0, "House Assets", "house_start", "house_end", house_start, house_end)
        self._build_xyz_row(1, "Landmark Assets", "landmark_start", "landmark_end", landmark_start, landmark_end)

    def area_env_value(self):
        if self.area_kind == "road":
            start = common.parse_xyz(self.area_vars["road_start"].get(), "Road cube start")
            end = common.parse_xyz(self.area_vars["road_end"].get(), "Road cube end")
            return f"{start[0]},{end[0]},{start[2]},{end[2]},{start[1]},{end[1]}"

        house_start = common.parse_xyz(self.area_vars["house_start"].get(), "House cube start")
        house_end = common.parse_xyz(self.area_vars["house_end"].get(), "House cube end")
        landmark_start = common.parse_xyz(self.area_vars["landmark_start"].get(), "Landmark cube start")
        landmark_end = common.parse_xyz(self.area_vars["landmark_end"].get(), "Landmark cube end")
        house = f"1,{house_start[0]},{house_end[0]},{house_start[2]},{house_end[2]},{house_start[1]},{house_end[1]}"
        landmark = f"2,{landmark_start[0]},{landmark_end[0]},{landmark_start[2]},{landmark_end[2]},{landmark_start[1]},{landmark_end[1]}"
        return f"{house};{landmark}"

    def set_extract_command(self, command):
        self.extract_button.configure(command=command)


class IntegerSlider(ttk.Frame):
    def __init__(self, master, text_var, minimum, maximum):
        super().__init__(master, style="Card.TFrame")
        self.text_var = text_var
        self.minimum = minimum
        self.maximum = maximum
        self.value_var = tk.IntVar(value=self._coerce(text_var.get()))
        self._tick_after_id = None
        self._last_tick_width = None
        tick_bg = self.tk.call("ttk::style", "lookup", "Card.TFrame", "-background") or self.cget("background")

        self.scale = ttk.Scale(self, from_=minimum, to=maximum, orient="horizontal", command=self._on_slide)
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
            self.ticks.create_line(x, 1, x, 8, fill=common.TICK)


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.window = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, event):
        if self.window or not self.text:
            return
        x = event.x_root + 12
        y = event.y_root + 12
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.window,
            text=self.text,
            padx=8,
            pady=5,
            bg=common.TOOLTIP_BG,
            fg=common.TOOLTIP_TEXT,
            font=common.ui_font(self.widget.winfo_toplevel().ui_font_family, 10),
            wraplength=280,
        )
        label.pack()

    def _hide(self, _event=None):
        if self.window:
            self.window.destroy()
            self.window = None


class WeightedProgressMixin:
    def _init_weighted_progress(self):
        self._progress_after_id = None
        self._progress_soft_target = 0.0

    def _build_progress_bar(self, row):
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(self, mode="determinate", variable=self.progress_var)
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

    actions_frame = ttk.Frame(config_frame, style="Card.TFrame")
    actions_frame.grid(row=0, column=7, sticky="e")

    if extra_actions:
        for column, (text, command) in enumerate(extra_actions):
            extra_button = ActionButton(
                actions_frame,
                text=text,
                command=command,
                width=max(common.BUTTON_WIDTH, len(text) + 1),
            )
            extra_button.grid(row=0, column=column, sticky="e", padx=(0, 6))

    action_column = len(extra_actions or [])
    action_button = ActionButton(actions_frame, text=action_text, command=action_command, width=common.BUTTON_WIDTH)
    action_button.grid(row=0, column=action_column, sticky="e")

    config_grid = ttk.Frame(config_frame, style="Card.TFrame")
    config_grid.grid(row=1, column=0, columnspan=8, sticky="ew", pady=(6, 0))
    for column in range(len(common.PREVIEW_CONFIG_GROUPS)):
        config_grid.columnconfigure(column, weight=1, uniform=uniform_name)

    for group_col, (_group_title, names) in enumerate(common.PREVIEW_CONFIG_GROUPS):
        group = ttk.LabelFrame(config_grid, text="", padding=6, style="Inset.TLabelframe")
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

