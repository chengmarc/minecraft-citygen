"""Render the images uploaded to Partner Center into dist/: the logos and the screenshots, in
<code>/, one folder per language. Also GitHub's social preview, docs/social-preview.png, uploaded in the repo's Settings, and the
README's three English screenshots, in docs/screenshots/.

They are drawn by the pages beside this script (logo.html, shots.html, social.html) from the app's own
files: its icon, the pictures in docs/pics/, and its window in each language, which capture_windows.py shoots first
from the cities replay_scenes.py builds. Uses Microsoft Edge, which comes with Windows, in headless mode.
SUBMISSION.md says where each image goes.

Run from the repo root: python store-listing/generator/render.py
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

GENERATOR = Path(__file__).resolve().parent
LISTING = GENERATOR.parent
OUTPUT = LISTING.parent / "dist"
EDGE_PROFILE = LISTING.parent / "build" / "edge-render"  # a profile of its own, so a running Edge isn't involved

# Every image is in every language, with captions.js's words, each in its own folder.
LANGUAGES = ("en", "de", "es", "fr", "ja", "pt", "ru", "zh")
SHOTS = ("promo", "size", "styles", "extract", "preview")
TILE = "store-logo-300.png"   # transparent around the icon

# What the README shows: the first screenshots in English, copied where git tracks them.
README_SCREENSHOTS = LISTING.parent / "docs" / "screenshots"
README_SHOTS = 3

# Each image: file (in dist/), page (with its hash), its size in CSS pixels, and its scale.
# Partner Center's sizes: screenshots 1366 x 768 or larger, box art 2160 x 2160, poster art 1440 x 2160, tile 300 x 300.
# GitHub's social preview: 1280 x 640, under 1 MB.
IMAGES = [
    *(
        (f"{code}/screenshot-{number}-{shot}.png", f"shots.html#{code}.{shot}", 1366, 768, 2)
        for code in LANGUAGES
        for number, shot in enumerate(SHOTS, 1)
    ),
    *((f"{code}/box-art-2160.png", f"logo.html#{code}", 1080, 1080, 2) for code in LANGUAGES),
    *((f"{code}/poster-art-1440x2160.png", f"logo.html#{code}", 720, 1080, 2) for code in LANGUAGES),
    *((f"{code}/{TILE}", f"logo.html#{code}.tile", 300, 300, 1) for code in LANGUAGES),
    ("../docs/social-preview.png", "social.html", 1280, 640, 1),
]


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
    from capture_windows import capture   # it needs the citygen package, which nothing else here does

    edge = find_edge()
    capture(edge, LANGUAGES)
    for folder in (OUTPUT / code for code in LANGUAGES):
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("*.png"):
            old.unlink()

    for name, page, width, height, scale in IMAGES:
        file = (OUTPUT / name).resolve()
        page_file, _, page_hash = page.partition("#")
        url = (GENERATOR / page_file).as_uri() + (f"#{page_hash}" if page_hash else "")
        # --virtual-time-budget lets the page load what it fetches before the shot is taken, without waiting in real time.
        args = [
            edge, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
            f"--user-data-dir={EDGE_PROFILE}", f"--force-device-scale-factor={scale}",
            f"--window-size={width},{height}", "--virtual-time-budget=5000", f"--screenshot={file}",
        ]
        if name.endswith(TILE):
            args.append("--default-background-color=00000000")
        subprocess.run([*args, url], check=False, capture_output=True)

        if not file.is_file():
            raise SystemExit(f"Edge didn't write {name}.")
        size = png_size(file)
        expected = (width * scale, height * scale)
        if size != expected:
            raise SystemExit(f"{name} is {size[0]} x {size[1]}, expected {expected[0]} x {expected[1]}.")
        print(f"{file.relative_to(LISTING.parent).as_posix()}  {size[0]} x {size[1]}")

    copy_readme_screenshots(OUTPUT / "en", README_SCREENSHOTS)


def copy_readme_screenshots(english: Path, folder: Path) -> None:
    """Copy the screenshots the README shows from ``english`` into ``folder``."""
    folder.mkdir(parents=True, exist_ok=True)
    for number, shot in enumerate(SHOTS[:README_SHOTS], 1):
        name = f"screenshot-{number}-{shot}.png"
        shutil.copyfile(english / name, folder / name)
        print(f"{(folder / name).relative_to(LISTING.parent).as_posix()}")


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("render.py runs on Windows, with Microsoft Edge.")
    main()
