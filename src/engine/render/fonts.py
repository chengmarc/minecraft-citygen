"""Label font lookup shared by every PNG renderer."""

from __future__ import annotations

from functools import lru_cache

from PIL import ImageFont


@lru_cache(maxsize=None)
def label_font(size):
    """Bold Arial when available, then Arial, then Pillow's built-in font."""
    for name in ("arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()
