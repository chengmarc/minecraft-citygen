"""Bootstrap helpers for Tcl/Tk on Windows Python installs."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _find_tcl_dir(root: Path, *names: str) -> Path | None:
    for name in names:
        candidate = root / name
        if candidate.is_dir():
            return candidate
    return None


def _prepend_path(env_key: str, value: str) -> None:
    existing = os.environ.get(env_key)
    if not existing:
        os.environ[env_key] = value
        return
    parts = existing.split(os.pathsep)
    if value not in parts:
        os.environ[env_key] = os.pathsep.join([value, *parts])


def configure_tcl_tk():
    base = Path(sys.base_prefix)
    tcl_root = base / "tcl"
    dll_root = base / "DLLs"
    tcl_library = _find_tcl_dir(tcl_root, "tcl8.7", "tcl8.6", "tcl8")
    tk_library = _find_tcl_dir(tcl_root, "tk8.7", "tk8.6")

    if dll_root.is_dir():
        _prepend_path("PATH", str(dll_root))

    if tcl_library is not None and (tcl_library / "init.tcl").is_file():
        os.environ.setdefault("TCL_LIBRARY", str(tcl_library).replace("\\", "/"))

    if tk_library is not None and (tk_library / "tk.tcl").is_file():
        os.environ.setdefault("TK_LIBRARY", str(tk_library).replace("\\", "/"))

    if tcl_root.is_dir() and "TCLLIBPATH" not in os.environ:
        roots = []
        if tcl_library is not None:
            roots.append(str(tcl_library).replace("\\", "/"))
        roots.append(str(tcl_root).replace("\\", "/"))
        os.environ["TCLLIBPATH"] = " ".join("{" + root + "}" for root in roots)
