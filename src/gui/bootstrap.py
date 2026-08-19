"""Bootstrap helpers for Tcl/Tk on Windows Python installs."""

from __future__ import annotations

import os
import sys


def configure_tcl_tk():
    tcl_root = os.path.normpath(os.path.join(sys.base_prefix, "tcl"))
    dll_root = os.path.normpath(os.path.join(sys.base_prefix, "DLLs"))
    tcl_library = os.path.join(tcl_root, "tcl8.6")
    tk_library = os.path.join(tcl_root, "tk8.6")
    if os.path.isdir(dll_root):
        os.environ["PATH"] = dll_root + os.pathsep + os.environ.get("PATH", "")
    if os.path.exists(os.path.join(tcl_library, "init.tcl")):
        os.environ["TCL_LIBRARY"] = tcl_library.replace("\\", "/")
    if os.path.exists(os.path.join(tk_library, "tk.tcl")):
        os.environ["TK_LIBRARY"] = tk_library.replace("\\", "/")
    if os.path.isdir(tcl_root):
        roots = [
            os.path.join(tcl_root, "tcl8.6").replace("\\", "/"),
            tcl_root.replace("\\", "/"),
        ]
        os.environ["TCLLIBPATH"] = " ".join("{" + root + "}" for root in roots)

