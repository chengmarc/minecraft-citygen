# Releasing

This repo publishes a Windows installer and a portable Windows zip as the
end-user deliverables.

The default release artifacts are:

- `dist/release/CityGen-setup.exe`
- `dist/release/CityGen-portable-windows.zip`

## Release Rules

- publish only the curated files under `dist/release`, not the raw `dist/portable`
  or `dist/onefile` build directories
- do not publish the standalone `CityGen.exe` unless there is a specific testing reason
- do not show a version number inside the app UI; the git tag is the release version of record
- keep packaging metadata intentional, but do not treat it as user-facing release branding

## Pre-Release Checklist

1. Freeze the scope for the release. Do not mix feature work into the release build pass.
2. Choose the release tag you intend to publish.
3. Update [CHANGELOG.md](CHANGELOG.md) with the release date and the final changes.
4. Run the test suite:

```bash
python -m unittest discover -s tests
```

5. Build the release artifacts:

```bash
python packaging/build_windows_release.py --clean
```

6. Confirm the only published artifacts in `dist/release` are
   `CityGen-setup.exe` and `CityGen-portable-windows.zip`.
7. Install the generated installer on a non-dev machine or a clean VM.
8. Smoke-test the real user flow:

- first launch succeeds
- Extraction tab opens and accepts a world path
- Preview completes successfully
- Generate completes successfully (city `.schem`, isometric render, and exported world)
- the exported world appears under `artifacts/saves/` and "Copy World" opens that folder
- the exported world loads in Minecraft and drops the player standing on the city
- installer uninstall works cleanly

9. Confirm output behavior:

- generated files land in the expected `artifacts/` folders
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

The standalone one-file executable is for testing only and should not be the
default public deliverable:

```bash
python packaging/build_windows_release.py --clean --include-standalone
```

This can additionally produce:

- `dist/release/CityGen.exe`

## Recommended Release Sequence

1. Choose the release tag.
2. Update changelog.
3. Run tests.
4. Build release artifacts.
5. Install and smoke-test installer.
6. Tag release.
7. Publish `CityGen-setup.exe` and `CityGen-portable-windows.zip`.
