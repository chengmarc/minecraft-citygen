"""Render every designed image of the app, by where it goes:

    promo/out/store/microsoft-store/<code>/  uploaded to Partner Center, one folder per language: the logos and the
                                             screenshots (../listing/SUBMISSION.md says where each goes)
    promo/out/social-preview.png             GitHub's social preview, uploaded in the repo's Settings -> Social preview
    promo/out/portfolio.png                  a square tile for the portfolio section of a job profile
    docs/app-icon.png, docs/screenshots/     what the README shows: the icon, and the first three English screenshots

They are drawn by the pages beside this script (logo.html, shots.html, social.html, portfolio.html) from the app's
own files: its icon, the pictures in docs/pics/, and its window in each language, which capture_windows.py shoots
first from the cities replay_scenes.py builds. Uses Microsoft Edge, which comes with Windows, in headless mode.

Git keeps only the README's images. Everything in promo/out/ is uploaded by hand, so it's made again whenever
it's needed, and never kept.

Run from the repo root: python promo/generator/render.py
With --no-store, only what doesn't need the app's window: the social preview, the portfolio tile and the README's
icon, in a few seconds.
"""

from __future__ import annotations

import argparse
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

GENERATOR = Path(__file__).resolve().parent
ROOT = GENERATOR.parents[1]
STORE = "promo/out/store/microsoft-store"
EDGE_PROFILE = ROOT / "build" / "edge-render"  # a profile of its own, so a running Edge isn't involved

# Every image is in every language, with captions.js's words, each in its own folder.
LANGUAGES = ("en", "de", "es", "fr", "ja", "pt", "ru", "zh")
SHOTS = ("promo", "size", "styles", "extract", "preview")

# What the README shows: the first screenshots in English, copied where git tracks them.
README_SCREENSHOTS = ROOT / "docs" / "screenshots"
README_SHOTS = 3

# Each image: file (from the repo root), page (with its hash), its size in CSS pixels, and its scale.
# Partner Center's sizes: screenshots 1366 x 768 or larger, box art 2160 x 2160, poster art 1440 x 2160, tile 300 x 300.
STORE_IMAGES = [
    *(
        (f"{STORE}/{code}/screenshot-{number}-{shot}.png", f"shots.html#{code}.{shot}", 1366, 768, 2)
        for code in LANGUAGES
        for number, shot in enumerate(SHOTS, 1)
    ),
    *((f"{STORE}/{code}/box-art-2160.png", f"logo.html#{code}", 1080, 1080, 2) for code in LANGUAGES),
    *((f"{STORE}/{code}/poster-art-1440x2160.png", f"logo.html#{code}", 720, 1080, 2) for code in LANGUAGES),
    *((f"{STORE}/{code}/store-logo-300.png", f"logo.html#{code}.tile.300", 300, 300, 1) for code in LANGUAGES),
]
# GitHub's social preview: 1280 x 640, under 1 MB. The portfolio tile: square, mostly seen as a small thumbnail.
OTHER_IMAGES = [
    ("promo/out/social-preview.png", "social.html", 1280, 640, 1),
    ("promo/out/portfolio.png", "portfolio.html", 1080, 1080, 1),
    ("docs/app-icon.png", "logo.html#en.tile.180", 180, 180, 1),
]
IMAGES = STORE_IMAGES + OTHER_IMAGES


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


def render(edge: str, name: str, page: str, width: int, height: int, scale: int) -> None:
    file = ROOT / name
    file.parent.mkdir(parents=True, exist_ok=True)
    page_file, _, page_hash = page.partition("#")
    url = (GENERATOR / page_file).as_uri() + (f"#{page_hash}" if page_hash else "")
    # --virtual-time-budget lets the page load what it fetches before the shot is taken, without waiting in real time.
    args = [
        edge, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
        f"--user-data-dir={EDGE_PROFILE}", f"--force-device-scale-factor={scale}",
        f"--window-size={width},{height}", "--virtual-time-budget=5000", f"--screenshot={file}",
    ]
    if ".tile." in page:   # transparent around the icon
        args.append("--default-background-color=00000000")
    file.unlink(missing_ok=True)
    subprocess.run([*args, url], check=False, capture_output=True)

    if not file.is_file():
        raise SystemExit(f"Edge didn't write {name}.")
    size = png_size(file)
    expected = (width * scale, height * scale)
    if size != expected:
        raise SystemExit(f"{name} is {size[0]} x {size[1]}, expected {expected[0]} x {expected[1]}.")
    print(f"{name}  {size[0]} x {size[1]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-store", action="store_true",
                        help="only the social preview, the portfolio tile and the README's icon")
    no_store = parser.parse_args().no_store

    edge = find_edge()
    if not no_store:
        from capture_windows import capture   # it needs the citygen package, which nothing else here does

        capture(edge, LANGUAGES)
        for folder in (ROOT / STORE / code for code in LANGUAGES):
            folder.mkdir(parents=True, exist_ok=True)
            for old in folder.glob("*.png"):
                old.unlink()

    for image in OTHER_IMAGES if no_store else IMAGES:
        render(edge, *image)

    if not no_store:
        copy_readme_screenshots(ROOT / STORE / "en", README_SCREENSHOTS)


def copy_readme_screenshots(english: Path, folder: Path) -> None:
    """Copy the screenshots the README shows from ``english`` into ``folder``."""
    folder.mkdir(parents=True, exist_ok=True)
    for number, shot in enumerate(SHOTS[:README_SHOTS], 1):
        name = f"screenshot-{number}-{shot}.png"
        shutil.copyfile(english / name, folder / name)
        print(f"{(folder / name).relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("render.py runs on Windows, with Microsoft Edge.")
    main()
