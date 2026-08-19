"""Interactive image viewer with pan, zoom, and smooth-zoom pyramids."""

from __future__ import annotations

import os
import tkinter as tk

import ttkbootstrap as ttk

from gui import common
from gui.pan_zoom import PanZoomMixin, viewer_resample

Image = common.Image
ImageTk = common.ImageTk

MAX_FULL_RENDER_PIXELS = 3_500_000
PAN_SETTLE_MS = 90
ZOOM_SETTLE_MS = 500


class ImageViewer(PanZoomMixin, ttk.Frame):
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
        self._display_image = None
        self._photo = None
        self._zoom = 1.0
        self._image_id = None
        self._message_id = None
        self._has_title = bool(title and show_title)
        self._layout_after_id = None
        self._refine_after_id = None
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
            bg=common.theme.CANVAS_BG,
            highlightthickness=0,
            bd=0,
            width=420,
            height=min_height,
        )
        self.canvas.grid(row=canvas_row, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(canvas_row, weight=1)

        self._bind_pan_zoom(on_press=self._start_pan, on_drag=self._pan)
        self.show_message(initial_message)

    def show_message(self, message):
        self._cancel_refined_render()
        self._source_image = None
        self._display_image = None
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
            fill=common.theme.CANVAS_TEXT,
            font=common.ui_font(font_family, 11),
            text=message,
            width=360,
        )
        self.canvas.configure(scrollregion=(0, 0, 420, 420))

    def load_image(self, image_path):
        self._cancel_refined_render()
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
            return

        self._source_image = Image.open(image_path).convert("RGBA")
        self._zoom_pyramid = self._build_zoom_pyramid()
        self._zoom = self._fit_zoom(self._source_image)
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

    def _render_image(self, center=False, anchor=None, interactive=False):
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
        self._refresh_display_image(interactive=interactive)
        self._update_scrollregion()

    def _cancel_refined_render(self):
        if self._refine_after_id is not None:
            self.after_cancel(self._refine_after_id)
            self._refine_after_id = None

    def _schedule_refined_render(self, delay_ms):
        if not self._smooth_zoom or self._source_image is None:
            return
        self._cancel_refined_render()
        self._refine_after_id = self.after(delay_ms, self._run_refined_render)

    def _run_refined_render(self):
        self._refine_after_id = None
        if self._source_image is None:
            return
        self._refresh_display_image(interactive=False)

    def _update_scrollregion(self):
        if self._image_id is None:
            return
        x, y = self._view_origin
        width, height = self._virtual_size
        self._apply_scrollregion((x, y, x + width, y + height))

    def _zoom_at(self, canvas_x, canvas_y, factor):
        if not self._source_image or self._image_id is None:
            return "break"
        x0, y0 = self._view_origin
        old_zoom = self._zoom
        source_x = (canvas_x - x0) / old_zoom
        source_y = (canvas_y - y0) / old_zoom
        self._zoom = self._clamp_zoom(old_zoom * factor)
        actual_factor = self._zoom / old_zoom
        width = max(1, int(self._source_image.width * self._zoom))
        height = max(1, int(self._source_image.height * self._zoom))
        self._view_origin = (
            canvas_x - source_x * self._zoom,
            canvas_y - source_y * self._zoom,
        )
        self._virtual_size = (width, height)
        if actual_factor > 1.0 and self._display_image is not None and Image is not None and ImageTk is not None:
            self._render_interactive_zoom_preview(canvas_x, canvas_y, actual_factor)
        else:
            self._refresh_display_image(interactive=True)
        self._update_scrollregion()
        self._schedule_refined_render(ZOOM_SETTLE_MS)
        return "break"

    def _start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def _pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        if self._use_viewport_rendering(*self._virtual_size):
            self._refresh_display_image(interactive=True)
            self._schedule_refined_render(PAN_SETTLE_MS)

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

    def _render_interactive_zoom_preview(self, canvas_x, canvas_y, factor):
        prev_left, prev_top = self.canvas.coords(self._image_id)
        prev_width, prev_height = self._display_image.size
        next_width = max(1, int(round(prev_width * factor)))
        next_height = max(1, int(round(prev_height * factor)))
        preview = self._display_image.resize((next_width, next_height), Image.Resampling.NEAREST)
        self._photo = ImageTk.PhotoImage(preview)
        self._display_image = preview
        self.canvas.itemconfigure(self._image_id, image=self._photo)
        self.canvas.coords(
            self._image_id,
            canvas_x - (canvas_x - prev_left) * factor,
            canvas_y - (canvas_y - prev_top) * factor,
        )

    def _refresh_display_image(self, interactive=False):
        if self._source_image is None:
            return
        width, height = self._virtual_size
        if self._use_viewport_rendering(width, height):
            self._render_viewport_image(interactive=interactive)
            return

        _source_scale, source_image = self._select_zoom_source(self._zoom)
        resample = viewer_resample(
            fast_zoom=self._fast_zoom,
            smooth_zoom=self._smooth_zoom,
            zoom=self._zoom,
            interactive=interactive,
        )
        image = source_image.resize((width, height), resample)
        self._photo = ImageTk.PhotoImage(image)
        self._display_image = image
        if self._image_id is None:
            self._image_id = self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            self.canvas.itemconfigure(self._image_id, image=self._photo)
        self.canvas.coords(self._image_id, *self._view_origin)

    def _render_viewport_image(self, interactive=False):
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
            self._display_image = image
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
            crop = crop.resize(
                (target_width, target_height),
                viewer_resample(
                    fast_zoom=self._fast_zoom,
                    smooth_zoom=self._smooth_zoom,
                    zoom=self._zoom,
                    interactive=interactive,
                ),
            )

        self._photo = ImageTk.PhotoImage(crop)
        self._display_image = crop
        if self._image_id is None:
            self._image_id = self.canvas.create_image(left, top, anchor="nw", image=self._photo)
        else:
            self.canvas.itemconfigure(self._image_id, image=self._photo)
            self.canvas.coords(self._image_id, left, top)
