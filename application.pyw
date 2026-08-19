"""Tkinter GUI entry point for the city-generation pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from gui.launcher import main


if __name__ == "__main__":
    main()
