# Changelog

All notable changes to this project should be documented in this file.

The format is based on Keep a Changelog, and versions should match the release version you publish.

## [Unreleased]

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
