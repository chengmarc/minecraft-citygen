"""What the window's local server serves: the page, its icons, and the images the app writes.

A plain WSGI app, which pywebview runs on 127.0.0.1. Each route serves one folder
and nothing outside it.
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from urllib.parse import quote, unquote

from config.path import APP_DATA, GUI_ICONS, RESOURCE_ROOT

STATIC = Path(__file__).resolve().parent / "static"
ROUTES = {
    "/files/": Path(APP_DATA),
    "/icons/": Path(GUI_ICONS),
    "/": STATIC,
}
# Single files, ahead of the routes: the app icon, which the page shows as the brand.
FILES = {"/app-icon.svg": Path(RESOURCE_ROOT) / "app-icon.svg"}
# Not left to the Windows registry, which can map .js to text/plain.
CONTENT_TYPES = {
    ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".png": "image/png", ".svg": "image/svg+xml",
}


def file_url(path):
    """The page's URL for a file under ``APP_DATA``, changing whenever the file does, or None if it's missing."""
    path = Path(path)
    try:
        relative = path.resolve().relative_to(Path(APP_DATA).resolve())
        version = int(path.stat().st_mtime_ns)
    except (ValueError, OSError):
        return None
    return f"/files/{quote(relative.as_posix())}?v={version}"


def _resolve(url_path):
    if url_path in FILES:
        return FILES[url_path] if FILES[url_path].is_file() else None
    for prefix, root in ROUTES.items():
        if url_path.startswith(prefix):
            relative = unquote(url_path[len(prefix):]) or "index.html"
            target = (root / relative).resolve()
            if target.is_file() and target.is_relative_to(root.resolve()):
                return target
            return None
    return None


def app(environ, start_response):
    target = _resolve(environ.get("PATH_INFO", "/"))
    if target is None or environ.get("REQUEST_METHOD", "GET") not in ("GET", "HEAD"):
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not found"]
    content_type = (
        CONTENT_TYPES.get(target.suffix.lower())
        or mimetypes.guess_type(target.name)[0]
        or "application/octet-stream"
    )
    start_response("200 OK", [
        ("Content-Type", content_type),
        ("Content-Length", str(os.path.getsize(target))),
        ("Cache-Control", "no-store"),
    ])
    if environ.get("REQUEST_METHOD") == "HEAD":
        return [b""]
    return [target.read_bytes()]
