"""Installed GUI entry point."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gui.bootstrap import configure_tcl_tk


def main() -> None:
    configure_tcl_tk()
    from gui.app import main as run_app

    run_app()


if __name__ == "__main__":
    main()
