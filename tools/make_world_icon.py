"""Draw the 64 x 64 save-list icon of the bundled world and of every exported city.

The app icon's scene (a grass block, two glass towers and a house) as pixel art on a 2:1
isometric grid, so it stays sharp at the size MC shows it. The app ships only the PNG.

Run from the repo root: python tools/make_world_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "src" / "config" / "default_world" / "icon.png"

SIZE = 64
OX, OY = 32, 28  # screen position of grid point (0, 0, 0)


def iso(i, j, z=0.0):
    """Grid (i to the right-front, j to the left-front, z up) to screen: 2 px across, 1 px down per cell."""
    return (OX + (i - j) * 2, OY + (i + j) * 1 - z)


def poly(d, pts, fill):
    d.polygon([iso(*p) for p in pts], fill=fill)


def box(d, i0, i1, j0, j1, z0, z1, top, left, right):
    poly(d, [(i1, j0, z0), (i1, j1, z0), (i1, j1, z1), (i1, j0, z1)], right)  # face at i = i1
    poly(d, [(i0, j1, z0), (i1, j1, z0), (i1, j1, z1), (i0, j1, z1)], left)   # face at j = j1
    poly(d, [(i0, j0, z1), (i1, j0, z1), (i1, j1, z1), (i0, j1, z1)], top)


def glass(d, i0, i1, j0, j1, z0, z1, left, right, inset=0.5, bottom=2, top=2):
    poly(d, [(i1, j0 + inset, z0 + bottom), (i1, j1 - inset, z0 + bottom), (i1, j1 - inset, z1 - top), (i1, j0 + inset, z1 - top)], right)
    poly(d, [(i0 + inset, j1, z0 + bottom), (i1 - inset, j1, z0 + bottom), (i1 - inset, j1, z1 - top), (i0 + inset, j1, z1 - top)], left)


def draw():
    img = Image.new("RGBA", (SIZE, SIZE))
    d = ImageDraw.Draw(img)
    # Sky: the app icon's blue, in bands so it reads as pixels, not a blur.
    bands = ["#5cc2f2", "#52b0ee", "#479ce9", "#3d87e3", "#3472dc", "#2c5ed6", "#2650cf", "#2145c6"]
    for y in range(SIZE):
        d.line([(0, y), (SIZE - 1, y)], fill=bands[min(y * len(bands) // SIZE, len(bands) - 1)])

    n = 13  # the platform is n x n cells
    # Platform: a soil slab under a grass top.
    box(d, 0, n, 0, n, -6, 0, "#8fd14f", "#8b5a2b", "#6b4321")
    poly(d, [(0, n, -2), (n, n, -2), (n, n, 0), (0, n, 0)], "#5f9e2c")    # grass over the soil's edge
    poly(d, [(n, 0, -2), (n, n, -2), (n, n, 0), (n, 0, 0)], "#4a8021")
    poly(d, [(0, 0, 0), (n, 0, 0), (n, n, 0), (0, n, 0)], "#8fd14f")
    # Roads: one each way through the front of the block.
    poly(d, [(7, 0, 0), (9, 0, 0), (9, n, 0), (7, n, 0)], "#3a3f45")
    poly(d, [(0, 8, 0), (n, 8, 0), (n, 10, 0), (0, 10, 0)], "#3a3f45")

    ivory = ("#f6eedc", "#e3d6bb", "#c8b898")
    glass_l, glass_r = "#3d9be0", "#2a6fb8"
    # Back left: the shorter tower.
    box(d, 1, 5, 2, 6, 0, 20, *ivory)
    glass(d, 1, 5, 2, 6, 0, 20, glass_l, glass_r)
    box(d, 2, 4, 3, 5, 20, 22, *ivory)
    # Back right: the tall tower, stepped at the top, with a spire.
    box(d, 10, 13, 1, 5, 0, 30, *ivory)
    glass(d, 10, 13, 1, 5, 0, 30, glass_l, glass_r)
    box(d, 10.5, 12.5, 1.5, 4.5, 30, 34, *ivory)
    box(d, 11, 12, 2.5, 3.5, 34, 40, *ivory)
    # Front: the house on the corner.
    box(d, 10, 13, 10.5, 13, 0, 6, *ivory)
    poly(d, [(13, 11.5, 1), (13, 12.5, 1), (13, 12.5, 4), (13, 11.5, 4)], glass_r)  # window
    poly(d, [(11, 13, 0), (12, 13, 0), (12, 13, 4), (11, 13, 4)], "#4a4038")          # door
    return img


if __name__ == "__main__":
    draw().save(OUT)
    print(OUT)
