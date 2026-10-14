"""Render the images uploaded to Partner Center into store/listing/.

They are drawn by the pages in store/ (logo.html, shots.html) from the app's own
files: its icon and the pictures in docs/pics/. Uses Microsoft Edge, which comes
with Windows, in headless mode, and nothing outside the standard library.
LISTING.md says where each image goes.

Run from the repo root: python store/render.py
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys
from pathlib import Path

STORE = Path(__file__).resolve().parent
OUT = STORE / "listing"
EDGE_PROFILE = STORE.parent / "build" / "edge-render"  # a profile of its own, so a running Edge isn't involved

# Each image: file, page (with its hash), its size in CSS pixels, and its scale.
# Partner Center's sizes: screenshots 1366 x 768 or larger, box art 2160 x 2160, poster art 1440 x 2160, tile 300 x 300.
IMAGES = [
    ("screenshot-1-promo.png", "shots.html#promo", 1366, 768, 2),
    ("screenshot-2-seeds.png", "shots.html#seeds", 1366, 768, 2),
    ("screenshot-3-styles.png", "shots.html#styles", 1366, 768, 2),
    ("screenshot-4-size.png", "shots.html#size", 1366, 768, 2),
    ("box-art-2160.png", "logo.html", 1080, 1080, 2),
    ("poster-art-1440x2160.png", "logo.html", 720, 1080, 2),
    ("store-logo-300.png", "logo.html#tile", 300, 300, 1),
]
TRANSPARENT = {"store-logo-300.png"}


def find_edge() -> str:
    for root in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if root:
            path = Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if path.is_file():
                return str(path)
    raise SystemExit("Microsoft Edge wasn't found.")


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        header = f.read(24)
    return struct.unpack(">II", header[16:24])


def main() -> None:
    edge = find_edge()
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()

    for name, page, width, height, scale in IMAGES:
        file = OUT / name
        page_file, _, page_hash = page.partition("#")
        url = (STORE / page_file).as_uri() + (f"#{page_hash}" if page_hash else "")
        # --virtual-time-budget lets the page load what it fetches before the shot is taken, without waiting in real time.
        args = [
            edge, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
            f"--user-data-dir={EDGE_PROFILE}", f"--force-device-scale-factor={scale}",
            f"--window-size={width},{height}", "--virtual-time-budget=5000", f"--screenshot={file}",
        ]
        if name in TRANSPARENT:
            args.append("--default-background-color=00000000")
        subprocess.run([*args, url], check=False, capture_output=True)

        if not file.is_file():
            raise SystemExit(f"Edge didn't write {name}.")
        size = png_size(file)
        expected = (width * scale, height * scale)
        if size != expected:
            raise SystemExit(f"{name} is {size[0]} x {size[1]}, expected {expected[0]} x {expected[1]}.")
        print(f"store/listing/{name}  {size[0]} x {size[1]}")


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("render.py runs on Windows, with Microsoft Edge.")
    main()
