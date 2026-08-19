# CityGen 0.2.1 Release Notes

Released on August 20, 2026.

This is a hot-fix release for the Windows installer build. There are no changes
to application code or generated output — it exists solely to make the packaged
0.2.0 executable start.

## The problem

The 0.2.0 Windows build failed immediately on launch with:

```
_tkinter.TclError: invalid command name "::msgcat::mcmset"
```

`ttkbootstrap` initializes localization at startup, which requires Tcl's
`msgcat` package (version 1.6+, for the `::msgcat::mcmset` command). That
package was not bundled, so the interpreter had no such command.

## The cause

The PyInstaller Tcl/Tk hook only collected the `tcl8.6/` and `tk8.6/` script
directories. The Tcl 8.x "module" packages — `msgcat`, `http`, `tcltest`, and
friends — ship as `.tm` files under a separate `tcl8/` directory that sits
*beside* `tcl8.6/`, not inside it, so `msgcat` was never included.

## The fix

The hook now also bundles the `tcl8/` module tree to the bundle root, where Tcl
looks for it (the module path is resolved relative to the interpreter library,
i.e. `[file dirname $tcl_library]/tcl8`). `package require msgcat` now succeeds
and the application starts normally.

## Upgrade notes

- No configuration or output changes.
- Rebuild the Windows installer to pick up the fix.

## Verification

- `python -m pytest`
- `python packaging/build_windows_release.py --clean`
- Launch the built executable and confirm the GUI opens.
