# CityGen 0.2.0 Release Notes

Released on August 20, 2026.

This is an internal refactor and maintenance release. It focuses on structure,
readability, consistency, and cross-platform support. There are no intended
changes to the generated output — the city constructor was verified to produce
byte-identical results (decoded) against the previous implementation.

## Highlights

- The large GUI widgets module was split into focused submodules, and the two
  image viewers now share a common pan/zoom base instead of duplicating it.
- The city constructor was decomposed into named stages and given readable
  identifiers.
- Path handling, imports, type-annotation imports, and the logger contract were
  made consistent across the codebase.
- The per-user data directory is now platform-aware instead of Windows-only.

## What Changed

### GUI

- Split `gui/widgets.py` into `viewers`, `region_dialog`, `controls`, `tooltip`,
  `progress`, `panels`, `config_frame`, and a shared `pan_zoom` module.
- Extracted a shared pan/zoom mixin, removing duplicated zoom, pan, and
  scroll-region logic across the two viewers.
- Replaced the mutable theme module globals with a single theme object.

### Pipeline and engine

- Decomposed `city_construct.run()` into named helper stages.
- Renamed terse identifiers, including the `Tile` dimension fields
  (`W/H/L` to `width/height/length`).
- Promoted `World._load_chunk` to a public `load_chunk` method.
- Collapsed redundant production-schematic path aliases.
- Documented the environment-override and module-reload invariant.

### Consistency

- Standardized path construction on `pathlib` (public constants remain strings).
- Applied `from __future__ import annotations` uniformly.
- Replaced initial-only aliased imports with explicit names.
- Unified the logger call contract to a single string argument.

### Compatibility

- Made the per-user data directory follow macOS and Linux conventions instead of
  assuming Windows.
- Added upper version bounds to declared dependencies.

## Fixes

- Narrowed overly broad exception handlers that could hide real failures, while
  keeping the intended top-level and worker error boundaries.
- Corrected stale file references and machine-specific absolute links in
  `docs/TECHNICAL.md`.

## Upgrade notes

- No configuration or output changes are expected.
- Any local tooling that imported the internal `gui.widgets` module should import
  from the new focused modules instead, and the GUI theme palette is now read
  from `gui.common.theme`.

## Verification

- `python -m pytest`
- `python packaging/build_windows_release.py --clean`
