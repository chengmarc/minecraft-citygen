# CityGen 0.3.0 Release Notes

Released on August 20, 2026.

This release follows the Tkinter-to-Qt migration with a structural cleanup of the
Qt GUI layer, a reduction of surrounding tooling debt, and a renderer palette fix.
Unlike 0.2.x, this release **does** change generated output: biome-tinted blocks
(leaves, grass, vines, water) now render in colour instead of gray, and the
WorldEdit auto-copy step has been removed.

## Highlights

- The 1,100-line `gui/qt_app.py` was split into focused modules, and the Qt image
  viewer gained a public overlay API so dialogs no longer reach into its internals.
- The renderer palette now honours Minecraft's biome tinting, so leaves and grass
  are green and water is blue instead of gray.
- `clear_cache.py` moved into `tools/` and now also clears build, packaging, and
  test caches.
- Dead code left over from the Tkinter era was removed, and the WorldEdit
  auto-copy step was retired.

## What Changed

### GUI structure

- Split `gui/qt_app.py` into `theme`, `workers`, `widgets`, `region_dialog`,
  `tabs`, and `app`.
- Flattened the Qt image-viewer factory into module-level classes with a direct
  `PySide6` import, and gave `QtImageViewer` a public overlay API
  (`image_rect`, `set_overlay_rect`, `clear_overlay`) so the region-selector
  dialog no longer touches private members.
- Replaced string-matched error handling with typed `SeedError`/`ConfigError`,
  and the hand-rolled argument loop with `argparse` (adds `--help` and a real
  `--no-custom-theme` flag).
- Centralized the brand palette and the label-to-value selector mapping, made the
  button-icon helper idempotent, and switched to the static `QFontDatabase` API.
- Added headless GUI unit tests covering argument parsing, style configuration,
  and widget value round-trips.

### Renderer

- The palette generator (`tools/update_render_colors.py`) now reads each model
  face's `tintindex` and multiplies grayscale colormap masks by a representative
  biome tint (plains foliage/grass, default water; birch and spruce use their
  fixed constants).
- Tinting is gated on the source texture actually being grayscale and on an
  explicit allow-list, so pre-coloured blocks (cherry and azalea leaves) are left
  untouched.
- `src/engine/color_render.csv` was regenerated from the 26.2 client jar.

### Tooling and cleanup

- Removed the WorldEdit auto-copy step and the `MC_CITY_WORLDEDIT_SCHEM` override.
  The final city schematic is still written to `artifacts/city/production/` as a
  WorldEdit-ready `.schem`.
- Moved `clear_cache.py` into `tools/` and expanded it to also clear `build/`,
  `dist/`, `*.egg-info/`, `.pytest_cache/`, and the startup error log.
- Deduplicated `numba` across the `speed`/`build` dependency extras.

## Fixes

- Replaced the deprecated `QFontDatabase()` instance call with the static form.
- Corrected stale "Tkinter" references in entry-point docstrings and comments.

## Upgrade notes

- Renders will look different: foliage and water now show their in-game colours.
  Regenerate any previews or city renders to pick up the new palette.
- The WorldEdit auto-copy is gone. If you relied on `MC_CITY_WORLDEDIT_SCHEM`,
  copy the schematic from `artifacts/city/production/` yourself instead.
- `clear_cache.py` now lives at `tools/clear_cache.py`; update any scripts that
  invoked it.
- Local tooling that imported `gui.qt_app` should import from the new modules
  (`gui.app`, `gui.tabs`, `gui.widgets`, ...).
- The `--custom-qt-theme` flag was removed (the theme is on by default); use
  `--no-custom-theme` to opt out.

## Verification

- `python -m pytest`
- `python packaging/build_windows_release.py --clean`
- Launch the built executable and confirm the GUI opens and renders show green
  foliage.
