"""Installed GUI entry point."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--qt-app"]:
        args = args[1:]

    from gui.qt_app import main as run_qt_app

    return run_qt_app(args)


if __name__ == "__main__":
    raise SystemExit(main())
