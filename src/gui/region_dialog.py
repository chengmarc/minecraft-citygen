"""Modal world-region selector with chunk-snapped drag selection."""

from __future__ import annotations

import sys
import threading
import tkinter as tk

import ttkbootstrap as ttk

from engine.render_topdown import render_topdown_preview
from gui import common
from gui.pan_zoom import PanZoomMixin

Image = common.Image
ImageTk = common.ImageTk
CHUNK_SIZE = 16


class RegionSelectorDialog(PanZoomMixin, ttk.Toplevel):
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
            bg=common.theme.CANVAS_BG,
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
            fill=common.theme.CANVAS_TEXT,
            font=common.ui_font(master.winfo_toplevel().ui_font_family, 11),
            text="Loading world preview...",
            width=720,
            tags=("status",),
        )
        self._bind_pan_zoom(on_press=self._on_press, on_drag=self._on_drag, on_release=self._on_release)

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
        except (OSError, AttributeError):
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
            except Exception as exc:  # boundary: show any preview-load failure in the dialog
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
            fill=common.theme.CANVAS_TEXT,
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
        self._zoom = self._fit_zoom(self.preview_image)
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
        self._apply_scrollregion(bbox)

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

    def _zoom_at(self, canvas_x, canvas_y, factor):
        if self.preview_image is None or self._image_id is None:
            return "break"
        view_x, view_y = self._canvas_point(canvas_x, canvas_y)
        x0, y0 = self.canvas.coords(self._image_id)
        source_x = (view_x - x0) / self._zoom
        source_y = (view_y - y0) / self._zoom
        self._zoom = self._clamp_zoom(self._zoom * factor)
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
            fill=common.theme.ACCENT,
            outline=common.theme.ACCENT,
            stipple="gray25",
            width=2,
            tags=("selection",),
        )

    def _apply(self):
        if self.selection_world is None:
            return
        self.on_apply(*self.selection_world)
        self.destroy()
