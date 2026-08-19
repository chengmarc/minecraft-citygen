# Releasing

This repo publishes a Windows installer as the primary end-user deliverable.

The default release artifact is:

- `dist/release/CityGen-setup.exe`

## Release Rules

- do not publish `dist/portable` or `dist/onefile` artifacts unless there is a specific testing reason
- version numbers should be kept consistent across package metadata, installer output, app title, and README text
- the current repo has a known naming mismatch: `pyproject.toml` is `0.1.0`, while the app/README still say `v0.5`
- resolve that mismatch intentionally before a public release instead of letting it drift

## Pre-Release Checklist

1. Freeze the scope for the release. Do not mix feature work into the release build pass.
2. Choose the release version and update all user-visible version strings together.
3. Update [CHANGELOG.md](CHANGELOG.md) with the release date and the final changes.
4. Run the test suite:

```bash
python -m unittest discover -s tests
```

5. Build the installer:

```bash
python scripts/build_windows_release.py --clean
```

6. Confirm the only published artifact in `dist/release` is `CityGen-setup.exe`.
7. Install the generated installer on a non-dev machine or a clean VM.
8. Smoke-test the real user flow:

- first launch succeeds
- Extraction tab opens and accepts a world path
- Preview completes successfully
- Render completes successfully
- installer uninstall works cleanly

9. Confirm output behavior:

- generated files land in the expected `artifacts/` folders
- WorldEdit export copy behavior is correct
- no unexpected dependency prompts appear at runtime

10. Tag the release in git after the installer has been verified.

## Build Prerequisites

Install build dependencies:

```bash
python -m pip install .[build]
```

The installer build includes CPU `numba` acceleration for rendering. CUDA is not required.

Inno Setup must be installed so `ISCC.exe` is available. The current build script supports:

- `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`
- `%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe`
- `%ProgramFiles%\Inno Setup 6\ISCC.exe`

## Optional Non-Release Artifacts

These are for testing only and should not be the default public deliverables:

```bash
python scripts/build_windows_release.py --clean --include-portable --include-standalone
```

This can additionally produce:

- `dist/release/CityGen-portable-windows.zip`
- `dist/release/CityGen.exe`

## Recommended Release Sequence

1. Update versions.
2. Update changelog.
3. Run tests.
4. Build installer.
5. Install and smoke-test installer.
6. Tag release.
7. Publish only `CityGen-setup.exe`.
