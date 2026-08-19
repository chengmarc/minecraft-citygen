"""Shared pan/zoom canvas behavior for the image viewers."""

from __future__ import annotations

from gui import common

Image = common.Image
ImageTk = common.ImageTk

ZOOM_STEP = 1.12
ZOOM_MIN = 0.05
ZOOM_MAX = 8.0


def viewer_resample(*, fast_zoom, smooth_zoom, zoom, interactive):
    if fast_zoom:
        return Image.Resampling.NEAREST
    if smooth_zoom:
        if interactive and zoom >= 1:
            return Image.Resampling.NEAREST
        return Image.Resampling.BILINEAR
    return Image.Resampling.NEAREST if zoom >= 1 else Image.Resampling.BILINEAR


class PanZoomMixin:
    """Shared zoom math and scrollregion updates for a host that owns ``self.canvas``.

    Hosts must own a ``self.canvas`` and a ``self._zoom`` attribute, and implement
    ``_schedule_layout`` and ``_zoom_at`` (the actual re-render differs per viewer).
    """

    def _bind_pan_zoom(self, *, on_press, on_drag, on_release=None):
        canvas = self.canvas
        canvas.bind("<Configure>", self._schedule_layout)
        canvas.bind("<Enter>", lambda _event: canvas.focus_set())
        canvas.bind("<MouseWheel>", self._on_zoom_wheel)
        canvas.bind("<Button-4>", lambda event: self._zoom_at(event.x, event.y, ZOOM_STEP))
        canvas.bind("<Button-5>", lambda event: self._zoom_at(event.x, event.y, 1 / ZOOM_STEP))
        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        if on_release is not None:
            canvas.bind("<ButtonRelease-1>", on_release)

    def _fit_zoom(self, image):
        if not image:
            return 1.0
        canvas_size = max(min(self.canvas.winfo_width(), self.canvas.winfo_height()), 1)
        longest_edge = max(image.width, image.height)
        return max(canvas_size / longest_edge, ZOOM_MIN)

    def _clamp_zoom(self, zoom):
        return min(max(zoom, ZOOM_MIN), ZOOM_MAX)

    def _on_zoom_wheel(self, event):
        factor = ZOOM_STEP if event.delta > 0 else 1 / ZOOM_STEP
        self._zoom_at(event.x, event.y, factor)
        return "break"

    def _apply_scrollregion(self, bbox):
        self.canvas.configure(
            scrollregion=(
                min(0, bbox[0]),
                min(0, bbox[1]),
                max(self.canvas.winfo_width(), bbox[2]),
                max(self.canvas.winfo_height(), bbox[3]),
            )
        )
