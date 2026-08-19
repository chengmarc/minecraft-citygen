import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gui import bootstrap


class ConfigureTclTkTests(unittest.TestCase):
    def test_configure_tcl_tk_sets_expected_environment_variables(self):
        with tempfile.TemporaryDirectory() as tempdir:
            base = Path(tempdir)
            dll_root = base / "DLLs"
            tcl_root = base / "tcl"
            tcl_library = tcl_root / "tcl8.6"
            tk_library = tcl_root / "tk8.6"
            dll_root.mkdir()
            tcl_library.mkdir(parents=True)
            tk_library.mkdir(parents=True)
            (tcl_library / "init.tcl").write_text("# init", encoding="utf-8")
            (tk_library / "tk.tcl").write_text("# tk", encoding="utf-8")

            with (
                mock.patch.object(bootstrap.sys, "base_prefix", str(base)),
                mock.patch.dict(os.environ, {}, clear=True),
            ):
                bootstrap.configure_tcl_tk()

                self.assertEqual(os.environ["PATH"], str(dll_root))
                self.assertEqual(os.environ["TCL_LIBRARY"], str(tcl_library).replace("\\", "/"))
                self.assertEqual(os.environ["TK_LIBRARY"], str(tk_library).replace("\\", "/"))
                self.assertEqual(
                    os.environ["TCLLIBPATH"],
                    " ".join(
                        [
                            "{" + str(tcl_library).replace("\\", "/") + "}",
                            "{" + str(tcl_root).replace("\\", "/") + "}",
                        ]
                    ),
                )

    def test_configure_tcl_tk_preserves_existing_explicit_values(self):
        with tempfile.TemporaryDirectory() as tempdir:
            base = Path(tempdir)
            dll_root = base / "DLLs"
            dll_root.mkdir()

            with (
                mock.patch.object(bootstrap.sys, "base_prefix", str(base)),
                mock.patch.dict(
                    os.environ,
                    {
                        "PATH": "C:\\existing",
                        "TCL_LIBRARY": "C:/custom/tcl",
                        "TK_LIBRARY": "C:/custom/tk",
                        "TCLLIBPATH": "{C:/custom/tcl}",
                    },
                    clear=True,
                ),
            ):
                bootstrap.configure_tcl_tk()

                self.assertEqual(os.environ["PATH"], str(dll_root) + os.pathsep + "C:\\existing")
                self.assertEqual(os.environ["TCL_LIBRARY"], "C:/custom/tcl")
                self.assertEqual(os.environ["TK_LIBRARY"], "C:/custom/tk")
                self.assertEqual(os.environ["TCLLIBPATH"], "{C:/custom/tcl}")


if __name__ == "__main__":
    unittest.main()
