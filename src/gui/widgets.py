"""Reusable GUI widgets and config-frame builders."""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk

import ttkbootstrap as ttk

from engine.render_topdown import render_topdown_preview
from gui import common

Image = common.Image
ImageTk = common.ImageTk
CHUNK_SIZE = 16
MAX_FULL_RENDER_PIXELS = 3_500_000


def _format_extraction_xyz(pos):
    return f"({common.format_xyz(pos)})"


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


class ImageViewer(ttk.Frame):
    def __init__(
        self,
        master,
        title,
        initial_message="",
        min_height=420,
        show_title=True,
        fast_zoom=False,
        smooth_zoom=False,
    ):
        super().__init__(master, padding=6)
        self.title = title
        self.image_path = None
        self._source_image = None
        self._photo = None
        self._zoom = 1.0
        self._image_id = None
        self._message_id = None
        self._has_title = bool(title and show_title)
        self._layout_after_id = None
        self._view_change_callback = None
        self._suspend_view_notifications = False
        self._fast_zoom = fast_zoom
        self._smooth_zoom = smooth_zoom
        self._zoom_pyramid = None
        self._view_origin = (0.0, 0.0)
        self._virtual_size = (0, 0)

        canvas_row = 1 if self._has_title else 0
        if self._has_title:
            ttk.Label(self, text=title).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.canvas = tk.Canvas(
            self,
            bg=common.CANVAS_BG,
            highlightthickness=0,
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
        self._zoom_pyramid = None
        self._view_origin = (0.0, 0.0)
        self._virtual_size = (0, 0)
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

    def set_view_change_callback(self, callback):
        self._view_change_callback = callback

    def sync_view_from(self, other):
        state = other._current_view_state()
        if state is None:
            return
        self._apply_view_state(state)

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
            self._view_origin = (0.0, 0.0)
            self._virtual_size = (self._photo.width(), self._photo.height())
            self.canvas.configure(scrollregion=(0, 0, self._photo.width(), self._photo.height()))
            self._notify_view_changed("load")
            return

        self._source_image = Image.open(image_path).convert("RGBA")
        self._zoom_pyramid = self._build_zoom_pyramid()
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
        x, y = self._view_origin
        width, height = self._virtual_size
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if width <= canvas_width:
            x = max((canvas_width - width) // 2, 0)
        if height <= canvas_height:
            y = max((canvas_height - height) // 2, 0)
        self._view_origin = (x, y)
        self._refresh_display_image()
        self._update_scrollregion()
        self._notify_view_changed("layout")

    def _initial_zoom(self):
        if not self._source_image:
            return 1.0
        canvas_size = max(min(self.canvas.winfo_width(), self.canvas.winfo_height()), 1)
        longest_edge = max(self._source_image.width, self._source_image.height)
        return max(canvas_size / longest_edge, 0.05)

    def _render_image(self, center=False, anchor=None, notify=True):
        if not self._source_image:
            return
        width = max(1, int(self._source_image.width * self._zoom))
        height = max(1, int(self._source_image.height * self._zoom))
        if center:
            x = max((self.canvas.winfo_width() - width) // 2, 0)
            y = max((self.canvas.winfo_height() - height) // 2, 0)
        elif anchor:
            canvas_x, canvas_y, source_x, source_y = anchor
            x = canvas_x - source_x * self._zoom
            y = canvas_y - source_y * self._zoom
        else:
            x, y = self._view_origin

        self._view_origin = (x, y)
        self._virtual_size = (width, height)
        self._refresh_display_image()
        self._update_scrollregion()
        if notify:
            self._notify_view_changed("zoom")

    def _update_scrollregion(self):
        if self._image_id is None:
            return
        x, y = self._view_origin
        width, height = self._virtual_size
        bbox = (
            x,
            y,
            x + width,
            y + height,
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
        x0, y0 = self._view_origin
        source_x = (canvas_x - x0) / self._zoom
        source_y = (canvas_y - y0) / self._zoom
        self._zoom = min(max(self._zoom * factor, 0.05), 8.0)
        self._render_image(anchor=(canvas_x, canvas_y, source_x, source_y))
        return "break"

    def _start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def _pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        if self._use_viewport_rendering(*self._virtual_size):
            self._refresh_display_image()
        self._notify_view_changed("pan")

    def _current_view_state(self):
        if self._image_id is None:
            return None
        return {
            "zoom": self._zoom,
            "coords": self._view_origin,
            "xview": self.canvas.xview()[0],
            "yview": self.canvas.yview()[0],
        }

    def _apply_view_state(self, state):
        if self._image_id is None:
            return
        self._suspend_view_notifications = True
        try:
            zoom_changed = abs(self._zoom - state["zoom"]) > 1e-9
            self._view_origin = tuple(state["coords"])
            if self._source_image is not None and zoom_changed:
                self._zoom = state["zoom"]
                self._render_image(notify=False)
            else:
                self._zoom = state["zoom"]
                self._refresh_display_image()
            self._update_scrollregion()
            self.canvas.xview_moveto(state["xview"])
            self.canvas.yview_moveto(state["yview"])
            if self._use_viewport_rendering(*self._virtual_size):
                self._refresh_display_image()
        finally:
            self._suspend_view_notifications = False

    def _notify_view_changed(self, reason):
        if self._suspend_view_notifications or self._view_change_callback is None:
            return
        state = self._current_view_state()
        if state is not None:
            self._view_change_callback(self, state, reason)

    def _build_zoom_pyramid(self):
        if self._source_image is None:
            return None
        levels = [(1.0, self._source_image)]
        if not self._smooth_zoom:
            return levels

        scale = 1.0
        current = self._source_image
        while min(current.width, current.height) > 192:
            next_width = max(1, current.width // 2)
            next_height = max(1, current.height // 2)
            current = current.resize((next_width, next_height), Image.Resampling.BILINEAR)
            scale /= 2.0
            levels.append((scale, current))
        return levels

    def _select_zoom_source(self, zoom):
        if not self._zoom_pyramid:
            return 1.0, self._source_image
        return min(
            self._zoom_pyramid,
            key=lambda item: max(item[0] / max(zoom, 0.05), max(zoom, 0.05) / item[0]),
        )

    def _use_viewport_rendering(self, width, height):
        return self._smooth_zoom and width * height > MAX_FULL_RENDER_PIXELS

    def _refresh_display_image(self):
        if self._source_image is None:
            return
        width, height = self._virtual_size
        if self._use_viewport_rendering(width, height):
            self._render_viewport_image()
            return

        _source_scale, source_image = self._select_zoom_source(self._zoom)
        if self._fast_zoom:
            resample = Image.Resampling.NEAREST
        elif self._smooth_zoom:
            resample = Image.Resampling.BILINEAR
        else:
            resample = Image.Resampling.NEAREST if self._zoom >= 1 else Image.Resampling.BILINEAR
        image = source_image.resize((width, height), resample)
        self._photo = ImageTk.PhotoImage(image)
        if self._image_id is None:
            self._image_id = self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            self.canvas.itemconfigure(self._image_id, image=self._photo)
        self.canvas.coords(self._image_id, *self._view_origin)

    def _render_viewport_image(self):
        source_scale, source_image = self._select_zoom_source(self._zoom)
        origin_x, origin_y = self._view_origin
        width, height = self._virtual_size
        canvas_left = self.canvas.canvasx(0)
        canvas_top = self.canvas.canvasy(0)
        canvas_right = canvas_left + max(self.canvas.winfo_width(), 1)
        canvas_bottom = canvas_top + max(self.canvas.winfo_height(), 1)

        left = max(origin_x, canvas_left)
        top = max(origin_y, canvas_top)
        right = min(origin_x + width, canvas_right)
        bottom = min(origin_y + height, canvas_bottom)

        if right <= left or bottom <= top:
            image = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            self._photo = ImageTk.PhotoImage(image)
            if self._image_id is None:
                self._image_id = self.canvas.create_image(origin_x, origin_y, anchor="nw", image=self._photo)
            else:
                self.canvas.itemconfigure(self._image_id, image=self._photo)
                self.canvas.coords(self._image_id, origin_x, origin_y)
            return

        src_left = max(0, int((left - origin_x) / self._zoom * source_scale))
        src_top = max(0, int((top - origin_y) / self._zoom * source_scale))
        src_right = min(source_image.width, max(src_left + 1, int((right - origin_x) / self._zoom * source_scale + 0.9999)))
        src_bottom = min(source_image.height, max(src_top + 1, int((bottom - origin_y) / self._zoom * source_scale + 0.9999)))
        crop = source_image.crop((src_left, src_top, src_right, src_bottom))
        target_width = max(1, int(round(right - left)))
        target_height = max(1, int(round(bottom - top)))
        if crop.size != (target_width, target_height):
            crop = crop.resize((target_width, target_height), Image.Resampling.BILINEAR)

        self._photo = ImageTk.PhotoImage(crop)
        if self._image_id is None:
            self._image_id = self.canvas.create_image(left, top, anchor="nw", image=self._photo)
        else:
            self.canvas.itemconfigure(self._image_id, image=self._photo)
            self.canvas.coords(self._image_id, left, top)


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


class RegionSelectorDialog(ttk.Toplevel):
    def __init__(self, master, title, save_path, start_xyz, end_xyz, on_apply):
        super().__init__(master=master)
        self.title(title)
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.resizable(False, False)

        self.save_path = save_path
        self.start_xyz = start_xyz
        self.end_xyz = end_xyz
        self.on_apply = on_apply
        self.preview_image = None
        self.preview_meta = None
        self.preview_photo = None
        self._image_id = None
        self._zoom = 1.0
        self._layout_after_id = None
        self._drag_mode = None
        self.selection_start = None
        self.selection_world = None

        shell = ttk.Frame(self, padding=8)
        shell.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            shell,
            bg=common.CANVAS_BG,
            highlightthickness=0,
            bd=0,
            width=780,
            height=500,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        self.canvas.create_text(
            20,
            20,
            anchor="nw",
            fill=common.CANVAS_TEXT,
            font=common.ui_font(master.winfo_toplevel().ui_font_family, 11),
            text="Loading world preview...",
            width=720,
            tags=("status",),
        )
        self.canvas.bind("<Configure>", self._schedule_layout)
        self.canvas.bind("<Enter>", lambda _event: self.canvas.focus_set())
        self.canvas.bind("<MouseWheel>", self._on_zoom_wheel)
        self.canvas.bind("<Button-4>", lambda event: self._zoom_at(event.x, event.y, 1.12))
        self.canvas.bind("<Button-5>", lambda event: self._zoom_at(event.x, event.y, 1 / 1.12))
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        self.status_var = tk.StringVar(value="Loading world preview...")
        ttk.Label(shell, textvariable=self.status_var).grid(
            row=1,
            column=0,
            sticky="w",
            pady=(8, 0),
        )

        actions = ttk.Frame(shell)
        actions.grid(row=2, column=0, sticky="e", pady=(10, 0))
        ttk.Button(actions, text="Cancel", command=self.destroy).grid(row=0, column=0, padx=(0, 6))
        self.apply_button = ttk.Button(actions, text="Use Selection", command=self._apply, state="disabled")
        self.apply_button.grid(row=0, column=1)

        self._set_initial_geometry()
        self.after(0, self._lock_window_frame)
        self._start_loading()

    def _set_initial_geometry(self):
        parent = self.master.winfo_toplevel()
        self.update_idletasks()
        width = 800
        height = 600
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = max(parent.winfo_width(), width)
        parent_height = max(parent.winfo_height(), height)
        x = max(parent_x + (parent_width - width) // 2, 0)
        y = max(parent_y + (parent_height - height) // 2, 0)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(width, height)
        self.maxsize(width, height)

    def _lock_window_frame(self):
        if sys.platform != "win32":
            return
        try:
            import ctypes

            hwnd = self.winfo_id()
            get_window_long = ctypes.windll.user32.GetWindowLongW
            set_window_long = ctypes.windll.user32.SetWindowLongW
            set_window_pos = ctypes.windll.user32.SetWindowPos
            gcl_style = -16
            ws_maximizebox = 0x00010000
            ws_thickframe = 0x00040000
            swp_nosize = 0x0001
            swp_nomove = 0x0002
            swp_nozorder = 0x0004
            swp_framechanged = 0x0020

            style = get_window_long(hwnd, gcl_style)
            style &= ~ws_maximizebox
            style &= ~ws_thickframe
            set_window_long(hwnd, gcl_style, style)
            set_window_pos(hwnd, 0, 0, 0, 0, 0, swp_nosize | swp_nomove | swp_nozorder | swp_framechanged)
        except Exception:
            pass

    def _start_loading(self):
        if Image is None or ImageTk is None:
            self.status_var.set("Pillow is required for the region selector preview.")
            return

        def worker():
            try:
                image, meta = render_topdown_preview(
                    self.save_path,
                    min(self.start_xyz[1], self.end_xyz[1]),
                    max(self.start_xyz[1], self.end_xyz[1]),
                )
            except Exception as exc:
                self.after(0, lambda: self._show_error(str(exc).strip() or "Failed to load world preview."))
                return
            self.after(0, lambda: self._show_preview(image, meta))

        threading.Thread(target=worker, daemon=True).start()

    def _show_error(self, message):
        self.canvas.delete("all")
        self._image_id = None
        self.preview_photo = None
        self.canvas.create_text(
            20,
            20,
            anchor="nw",
            fill=common.CANVAS_TEXT,
            font=common.ui_font(self.winfo_toplevel().ui_font_family, 11),
            text=message,
            width=720,
        )
        self.status_var.set(message)

    def _show_preview(self, image, meta):
        self.preview_image = image
        self.preview_meta = meta
        self.canvas.delete("all")
        self._image_id = None
        self._zoom = self._initial_zoom()
        self._render_preview(center=True)
        self._set_selection_from_world(self.start_xyz, self.end_xyz)
        self.status_var.set("Hold Shift and drag to snap-select chunks.")

    def _schedule_layout(self, _event=None):
        if self.preview_image is None or self.preview_photo is None or self._image_id is None:
            return
        if self._layout_after_id is not None:
            self.after_cancel(self._layout_after_id)
        self._layout_after_id = self.after(60, self._apply_layout)

    def _apply_layout(self):
        self._layout_after_id = None
        if self._image_id is None or self.preview_photo is None:
            return
        x, y = self.canvas.coords(self._image_id)
        width = self.preview_photo.width()
        height = self.preview_photo.height()
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if width <= canvas_width:
            x = max((canvas_width - width) // 2, 0)
        if height <= canvas_height:
            y = max((canvas_height - height) // 2, 0)
        self.canvas.coords(self._image_id, x, y)
        self._update_scrollregion()
        self._redraw_selection()

    def _initial_zoom(self):
        if self.preview_image is None:
            return 1.0
        canvas_size = max(min(self.canvas.winfo_width(), self.canvas.winfo_height()), 1)
        longest_edge = max(self.preview_image.width, self.preview_image.height)
        return max(canvas_size / longest_edge, 0.05)

    def _render_preview(self, center=False, anchor=None):
        if self.preview_image is None:
            return
        width = max(1, int(self.preview_image.width * self._zoom))
        height = max(1, int(self.preview_image.height * self._zoom))
        resample = Image.Resampling.NEAREST if self._zoom >= 1 else Image.Resampling.BILINEAR
        image = self.preview_image.resize((width, height), resample)
        self.preview_photo = ImageTk.PhotoImage(image)

        if self._image_id is None:
            self._image_id = self.canvas.create_image(0, 0, anchor="nw", image=self.preview_photo, tags=("preview",))
        else:
            self.canvas.itemconfigure(self._image_id, image=self.preview_photo)

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
        self._redraw_selection()

    def _update_scrollregion(self):
        if self._image_id is None:
            return
        bbox = self.canvas.bbox(self._image_id) or (
            0,
            0,
            self.preview_photo.width() if self.preview_photo else 0,
            self.preview_photo.height() if self.preview_photo else 0,
        )
        self.canvas.configure(
            scrollregion=(
                min(0, bbox[0]),
                min(0, bbox[1]),
                max(self.canvas.winfo_width(), bbox[2]),
                max(self.canvas.winfo_height(), bbox[3]),
            )
        )

    def _canvas_point(self, x, y):
        return self.canvas.canvasx(x), self.canvas.canvasy(y)

    def _clamp_image_point(self, x, y):
        if self.preview_photo is None or self._image_id is None or self.preview_image is None:
            return None
        canvas_x, canvas_y = self._canvas_point(x, y)
        ox, oy = self.canvas.coords(self._image_id)
        ix = min(max((canvas_x - ox) / self._zoom, 0), self.preview_image.width - 1)
        iy = min(max((canvas_y - oy) / self._zoom, 0), self.preview_image.height - 1)
        return ix, iy

    def _image_point_to_world(self, point):
        if point is None or self.preview_meta is None:
            return None
        ix, iy = point
        span_x = self.preview_meta["x1"] - self.preview_meta["x0"] + 1
        span_z = self.preview_meta["z1"] - self.preview_meta["z0"] + 1
        world_x = self.preview_meta["x0"] + min(int(ix * self.preview_meta["step"]), span_x - 1)
        world_z = self.preview_meta["z0"] + min(int(iy * self.preview_meta["step"]), span_z - 1)
        return world_x, world_z

    def _chunk_at_canvas_point(self, x, y):
        world_point = self._image_point_to_world(self._clamp_image_point(x, y))
        if world_point is None:
            return None
        world_x, world_z = world_point
        return world_x // CHUNK_SIZE, world_z // CHUNK_SIZE

    def _on_zoom_wheel(self, event):
        factor = 1.12 if event.delta > 0 else 1 / 1.12
        self._zoom_at(event.x, event.y, factor)
        return "break"

    def _zoom_at(self, canvas_x, canvas_y, factor):
        if self.preview_image is None or self._image_id is None:
            return "break"
        view_x, view_y = self._canvas_point(canvas_x, canvas_y)
        x0, y0 = self.canvas.coords(self._image_id)
        source_x = (view_x - x0) / self._zoom
        source_y = (view_y - y0) / self._zoom
        self._zoom = min(max(self._zoom * factor, 0.05), 8.0)
        self._render_preview(anchor=(view_x, view_y, source_x, source_y))
        return "break"

    def _on_press(self, event):
        if self.preview_image is None:
            return
        if event.state & 0x0001:
            chunk = self._chunk_at_canvas_point(event.x, event.y)
            if chunk is None:
                return
            self._drag_mode = "select"
            self.selection_start = chunk
            self._update_selection(chunk, chunk)
            return
        self._drag_mode = "pan"
        self.selection_start = None
        self.canvas.scan_mark(event.x, event.y)

    def _on_drag(self, event):
        if self._drag_mode == "select" and self.selection_start is not None:
            chunk = self._chunk_at_canvas_point(event.x, event.y)
            if chunk is None:
                return
            self._update_selection(self.selection_start, chunk)
            return
        if self._drag_mode == "pan":
            self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_release(self, event):
        if self._drag_mode == "select" and self.selection_start is not None:
            chunk = self._chunk_at_canvas_point(event.x, event.y)
            if chunk is not None:
                self._update_selection(self.selection_start, chunk)
        self.selection_start = None
        self._drag_mode = None

    def _update_selection(self, first, second):
        if self.preview_meta is None:
            return
        chunk_x0, chunk_x1 = sorted((int(first[0]), int(second[0])))
        chunk_z0, chunk_z1 = sorted((int(first[1]), int(second[1])))
        world_x0 = max(self.preview_meta["x0"], chunk_x0 * CHUNK_SIZE)
        world_x1 = min(self.preview_meta["x1"], (chunk_x1 + 1) * CHUNK_SIZE - 1)
        world_z0 = max(self.preview_meta["z0"], chunk_z0 * CHUNK_SIZE)
        world_z1 = min(self.preview_meta["z1"], (chunk_z1 + 1) * CHUNK_SIZE - 1)
        self.selection_world = (
            (world_x0, self.start_xyz[1], world_z0),
            (world_x1, self.end_xyz[1], world_z1),
        )
        self._redraw_selection()
        self.apply_button.configure(state="normal")
        self.status_var.set(
            f"Selection: x {world_x0} to {world_x1}, z {world_z0} to {world_z1} "
            f"({chunk_x1 - chunk_x0 + 1} x {chunk_z1 - chunk_z0 + 1} chunks)"
        )

    def _set_selection_from_world(self, start_xyz, end_xyz):
        if self.preview_meta is None or self.preview_image is None:
            return
        chunk_x0 = min(start_xyz[0], end_xyz[0]) // CHUNK_SIZE
        chunk_x1 = max(start_xyz[0], end_xyz[0]) // CHUNK_SIZE
        chunk_z0 = min(start_xyz[2], end_xyz[2]) // CHUNK_SIZE
        chunk_z1 = max(start_xyz[2], end_xyz[2]) // CHUNK_SIZE
        self._update_selection((chunk_x0, chunk_z0), (chunk_x1, chunk_z1))

    def _redraw_selection(self):
        self.canvas.delete("selection")
        if (
            self.selection_world is None
            or self.preview_meta is None
            or self.preview_image is None
            or self._image_id is None
        ):
            return
        step = self.preview_meta["step"]
        ox, oy = self.canvas.coords(self._image_id)
        start, end = self.selection_world
        world_x0 = max(self.preview_meta["x0"], min(start[0], end[0]))
        world_x1 = min(self.preview_meta["x1"], max(start[0], end[0]))
        world_z0 = max(self.preview_meta["z0"], min(start[2], end[2]))
        world_z1 = min(self.preview_meta["z1"], max(start[2], end[2]))
        self.canvas.create_rectangle(
            ox + ((world_x0 - self.preview_meta["x0"]) / step) * self._zoom,
            oy + ((world_z0 - self.preview_meta["z0"]) / step) * self._zoom,
            ox + ((world_x1 + 1 - self.preview_meta["x0"]) / step) * self._zoom,
            oy + ((world_z1 + 1 - self.preview_meta["z0"]) / step) * self._zoom,
            fill=common.ACCENT,
            outline=common.ACCENT,
            stipple="gray25",
            width=2,
            tags=("selection",),
        )

    def _apply(self):
        if self.selection_world is None:
            return
        self.on_apply(*self.selection_world)
        self.destroy()


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


class IntegerSlider(ttk.Frame):
    def __init__(self, master, text_var, minimum, maximum):
        super().__init__(master)
        self.text_var = text_var
        self.minimum = minimum
        self.maximum = maximum
        self.value_var = tk.IntVar(value=self._coerce(text_var.get()))
        self._tick_after_id = None
        self._last_tick_width = None
        tick_bg = common.APP_BG

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
