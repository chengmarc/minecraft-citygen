# Changelog

All notable changes to this project should be documented in this file.

The format is based on Keep a Changelog, and versions should match the release version you publish.

## [Unreleased]

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
