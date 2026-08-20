# Changelog

All notable changes to this project should be documented in this file.

The format is based on Keep a Changelog, and versions should match the release version you publish.

## [Unreleased]

## [0.3.0] - 2026-08-20

This release follows up the Tkinter-to-Qt migration with a structural cleanup of
the GUI layer and surrounding tooling.

### Changed

- split the monolithic `gui/qt_app.py` into focused modules (`theme`, `workers`, `widgets`, `region_dialog`, `tabs`, `app`) and flattened the Qt image-viewer factory into module-level classes with a direct PySide6 import
- gave `QtImageViewer` a public overlay API so the region-selector dialog no longer reaches into private members
- replaced string-matched error handling with typed `SeedError`/`ConfigError`, and the hand-rolled argument loop with `argparse` (adds `--help` and a real `--no-custom-theme` flag)
- centralized the brand palette and the label-to-value selector mapping, and made the button-icon helper idempotent
- moved `clear_cache.py` into `tools/` and expanded it to also clear `build/`, `dist/`, `*.egg-info/`, `.pytest_cache/`, and the startup error log
- deduplicated `numba` across the `speed`/`build` dependency extras

### Removed

- removed the WorldEdit auto-copy step and the `MC_CITY_WORLDEDIT_SCHEM` override; the final city schematic is still written to `artifacts/city/production/` as a WorldEdit-ready `.schem`
- deleted dead code left over from the Tkinter era (unused arguments, duplicated helpers, stale flags, and unreachable region/format branches)

### Fixed

- replaced the deprecated `QFontDatabase()` instance call with the static form
- corrected stale “Tkinter” references in entry-point docstrings and comments

### Added

- headless GUI unit tests covering argument parsing, style configuration, and widget value round-trips

## [0.2.1] - 2026-08-20

This is a hot-fix release for the Windows installer build. There are no changes
to application code or generated output.

### Fixed

- fixed the frozen Windows build failing to start with `invalid command name "::msgcat::mcmset"`: the PyInstaller Tcl/Tk hook now bundles the Tcl 8.x module tree (`tcl8/`), which contains `msgcat` and other `.tm` packages that ship alongside — not inside — the `tcl8.6/` script directory. `ttkbootstrap`'s localization requires msgcat 1.6+ at startup.

## [0.2.0] - 2026-08-20

This is an internal refactor and maintenance release. There are no intended
changes to generated output: the city constructor was verified to produce
byte-identical results (decoded) against the previous implementation.

### Changed

- reorganized the monolithic GUI widgets module into focused submodules (image viewer, region-selector dialog, buttons/sliders, tooltip, progress, extraction panel, config frame) and extracted a shared pan/zoom base for the two viewers
- decomposed the city constructor into named stages and renamed terse identifiers, including the `Tile` dimension fields, for readability
- standardized path construction on `pathlib`, applied `from __future__ import annotations` uniformly, replaced initial-only aliased imports with explicit names, and unified the logger call contract to a single string
- replaced the mutable theme module globals with a single theme object
- made the per-user data directory platform-aware (macOS and Linux conventions) instead of Windows-only
- added upper version bounds to declared dependencies
- documented the pipeline environment-override and module-reload invariant

### Fixed

- narrowed overly broad exception handlers that could mask real failures, while keeping the intended top-level and worker error boundaries
- corrected stale file references and machine-specific absolute links in `docs/TECHNICAL.md`

## [0.1.0] - 2026-08-19

### Added

- installable project metadata and command entry points for the GUI and environment doctor
- a bundled default Minecraft world that ships with the app
- Windows installer build pipeline with PyInstaller, Inno Setup, and local packaging hooks for Tcl/Tk
- installer-only release flow with a documented Windows release command
- release support docs in `README.md`, plus this changelog and `RELEASING.md`
- regression tests for path discovery and isometric renderer fallback behavior

### Changed

- hard-coded machine-specific default paths were replaced with bundled defaults and explicit environment overrides
- frozen builds now package Tcl/Tk explicitly instead of relying on PyInstaller's broken auto-detection on this Python install
- the isometric renderer now works without `numba`, while using CPU `numba` acceleration when it is available
- release artifacts are now published to `dist/release`, with `CityGen-setup.exe` as the primary deliverable

### Fixed

- missing runtime dependencies in project metadata
- Windows-only output-folder behavior replaced with a cross-platform helper
- clearer extraction errors when the configured world path is missing
- packaged app startup failure caused by missing `tkinter` in the frozen build
