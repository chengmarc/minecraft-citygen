# CityGen 0.1.0 Release Notes

Released on August 19, 2026.

## Highlights

- The project now uses a `src/` package layout, which makes packaging and installs cleaner.
- CityGen can now be installed and launched with command entry points instead of relying on repo-local execution only.
- CityGen now ships with a bundled default Minecraft world and a fixed default export target.
- Windows release packaging now has a defined installer flow built around PyInstaller and Inno Setup.
- The isometric renderer now works even when `numba` is not installed, while still using CPU `numba` acceleration when available.

## What Changed

### Packaging and runtime

- Added project metadata and dependencies in `pyproject.toml`.
- Added `citygen` and `citygen-doctor` command entry points.
- Moved application code under `src/`.
- Added runtime path handling for source, installed, and frozen builds.
- Added a first-run environment doctor for dependency and path checks.

### Minecraft path handling

- Replaced machine-specific defaults with a bundled default world.
- Standardized the default `.schem` export copy target to `artifacts/worldedit`.
- Improved extraction failures when the configured world path is missing.

### Windows distribution

- Added a Windows installer build script.
- Added PyInstaller hooks for Tcl/Tk so the GUI can start reliably in frozen builds.
- Standardized release output under `dist/release/`.
- Set `CityGen-setup.exe` as the primary release artifact.

### Documentation

- Reorganized screenshots and technical docs under `docs/`.
- Added release process documentation and changelog support.
- Kept `README.md` at repo root and moved the engineering reference to `docs/TECHNICAL.md`.

### Tests

- Added regression coverage for path discovery.
- Added regression coverage for the isometric renderer fallback path.
- Added test bootstrapping for the new `src/` layout.

## User-visible fixes

- Fixed missing runtime dependency declarations in packaging metadata.
- Replaced Windows-only folder-opening logic with a cross-platform helper.
- Fixed frozen-app startup issues caused by missing `tkinter` packaging.

## Upgrade notes

- Direct imports now resolve from `src/`, so any local tooling that assumed top-level `config/`, `engine/`, `gui`, or `pipeline` paths should be updated.
- Technical documentation now lives at `docs/TECHNICAL.md`.
- Demo images now live under `docs/`.

## Verification

- `python -m pytest`
- `python src/config/doctor.py`
