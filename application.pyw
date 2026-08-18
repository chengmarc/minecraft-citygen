"""Tkinter GUI entry point for the city-generation pipeline."""

from __future__ import annotations

from gui.app import main
from gui.bootstrap import configure_tcl_tk


configure_tcl_tk()


if __name__ == "__main__":
    main()
