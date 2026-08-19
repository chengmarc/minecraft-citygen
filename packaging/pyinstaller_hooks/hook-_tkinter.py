"""Collect Tcl/Tk script directories for frozen CityGen builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _collect_tree(source: Path, dest_root: str) -> list[tuple[str, str]]:
    datas: list[tuple[str, str]] = []
    if not source.is_dir():
        return datas
    for root, _dirs, files in os.walk(source):
        root_path = Path(root)
        relative = root_path.relative_to(source)
        dest_dir = Path(dest_root, relative).as_posix() if relative.parts else dest_root
        for name in files:
            datas.append((str(root_path / name), dest_dir))
    return datas


base_tcl = Path(sys.base_prefix) / "tcl"
datas = [
    *_collect_tree(base_tcl / "tcl8.6", "_tcl_data"),
    *_collect_tree(base_tcl / "tk8.6", "_tk_data"),
]
