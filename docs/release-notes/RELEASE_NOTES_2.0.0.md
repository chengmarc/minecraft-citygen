# MC CityGen 2.0.0 Release Notes

Released on TBD.

MC CityGen 2.0.0 rebuilds the window: it is now an HTML page in Microsoft Edge
WebView2, was Qt, with a new look around the same three tabs. Everything the
app writes, settings included, now lives in one `appdata/` folder, and the
first launch moves your existing data there. The source is one Python package,
and the same seeds still make the same cities.

## Highlights

- **A new window.** The app runs in WebView2 (through pywebview), was Qt
  (PySide6). Same three tabs, settings and outputs; saved settings carry over,
  and the release no longer bundles Qt.
- **A new look.** The tabs are numbered steps that check off as they're done.
  Each tab's settings and progress sit in one panel below the pictures, which
  are labelled and have zoom buttons. The progress bar is the strip of ground
  along the window's bottom, with each step's name inside it.
- **One data folder.** Settings and every output are in `appdata/`, was
  `artifacts/` and `src/config/citygen.json`.

## What Changed

### GUI

- The big buttons share one green style. Basic/Advanced Settings is now More
  settings, and the Build tab's Copy is now Worlds.
- Contact sheets are transparent, was near-black, with dark labels outlined in
  white, so the road and building pieces sit on the window's sky.
- Extract has a Reset beside its progress bar: back to the sample world and its
  areas.
- `--debug` allows the page's developer tools (F12). `--qt-style` and
  `--no-custom-theme` are gone.

### Packaging

- The build writes only what ships to `dist/`: `MC CityGen-setup.exe`, and
  `MC CityGen.exe` and `MC CityGen.msix` when asked for, was `dist/release/`
  and `dist/store/`. Intermediates are in `build/packaging/`.
- The uninstaller's "delete generated data" option removes both the new
  `appdata/` folder and the old ones.

### Source and repository

- The source is one package, `src/citygen/`, was `config/`, `engine/`,
  `pipeline/` and `gui/`; its guide is `src/README.md`.
- A checkout runs with `pythonw src/application.pyw`.
- The Store listing is in `store-listing/`, was `store/`. Release notes are in
  `docs/release-notes/`, was `docs/release/`.
- The block-colour generator is `src/citygen/data/color_render_update.py`,
  beside the CSV it writes. The other repo scripts are gone.

## Upgrade Notes

- The app needs the Microsoft Edge WebView2 Runtime, which comes with
  Windows 11 and most of Windows 10. Without it, the app opens the runtime's
  download page instead of starting.
- The first launch moves an existing `artifacts/` folder and saved settings into
  `appdata/`. If `appdata/` already exists, nothing is merged: the old folders
  stay where they are, for you to copy from.
- Shortcuts or scripts that pass `--qt-style` or `--no-custom-theme` must drop
  them.
- Publish only `MC CityGen-setup.exe` to GitHub. Upload `MC CityGen.msix` to
  Partner Center, not to GitHub.

## Verification

- `python -m pytest -q`
- `python packaging/build_windows_release.py --clean --msix`
