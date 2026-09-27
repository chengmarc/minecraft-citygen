# Releasing — Windows builds

How the source tree becomes the two end-user deliverables — a Windows installer
and a portable Windows zip — built by [packaging/](../packaging). Nothing in
`packaging/` ships inside the app.

← Back to the [source architecture overview](../src/README.md).

## How-to guides

### Cut a release

1. Freeze the scope. Do not mix feature work into the release build pass.
2. Choose the release tag. The git tag is the release version of record; bump
   the other places that spell the version out to match:
   - `version` in [pyproject.toml](../pyproject.toml) — the build script
     passes it to the installer as `AppVersion`
   - the version badge and the two download URLs in the root
     [README.md](../README.md)
3. Update [CHANGELOG.md](CHANGELOG.md) with the release date and
   the final changes, and add `docs/release/RELEASE_NOTES_<version>.md`.
4. Run the test suite:

   ```bash
   python -m pytest -q
   ```

   Use pytest, not `unittest discover`: [tests/conftest.py](../tests/conftest.py)
   puts `src/` on `sys.path`, and only pytest loads it.
5. Build the release artifacts (see [Build prerequisites](#build-prerequisites)):

   ```bash
   python packaging/build_windows_release.py --clean
   ```

6. Confirm `dist/release/` holds exactly the two
   [release artifacts](#release-artifacts).
7. Install the installer on a non-dev machine or a clean VM and smoke-test the
   real user flow:
   - first launch succeeds, with no unexpected dependency prompts
   - the Extract tab accepts a world path and extraction completes
   - Preview completes
   - Build completes: city `.schem`, isometric render, and exported world
   - generated files land in the expected `artifacts/` folders; the exported
     world appears under `artifacts/05_world/saves/` and "Copy World" opens it
   - the exported world loads in Minecraft with the player standing on the city
   - uninstall works cleanly
8. Tag the release in git only after the installer has been verified.
9. Publish the two release artifacts.

### Build a standalone exe for testing

```bash
python packaging/build_windows_release.py --clean --include-standalone
```

This additionally writes `dist/release/Minecraft CityGen.exe`. It is for
testing only; do not publish it.

### Build the Microsoft Store package

The Store takes an MSIX package and signs it itself, so no code-signing
certificate is needed. The MSIX is uploaded to Partner Center, not published
with the GitHub release.

1. One time: copy the three values from Partner Center > the app > Product
   identity into `MSIX_IDENTITY_NAME`, `MSIX_PUBLISHER`, and
   `MSIX_PUBLISHER_DISPLAY_NAME` in
   [build_windows_release.py](../packaging/build_windows_release.py).
2. Build:

   ```bash
   python packaging/build_windows_release.py --clean --msix
   ```

   This additionally writes `dist/store/Minecraft CityGen.msix`.
3. Smoke-test the packaged app before uploading. With Developer Mode on,
   register the unpacked layout instead of installing the unsigned MSIX:

   ```powershell
   Add-AppxPackage -Register "build\release\msix\AppxManifest.xml"
elease\msix\AppxManifest.xml"
   ```

   Run the same checks as the installer smoke test. Generated files should land
   under `%LOCALAPPDATA%\Packages\<package family name>\LocalCache\Local\Minecraft CityGen\`,
   and the saves folder should open in Explorer. Remove it afterwards with
   `Get-AppxPackage chengmarc.MCCityGen | Remove-AppxPackage`.
4. Upload the `.msix` in a new Partner Center submission.

### Keep the build in step with a new pipeline step

Stage step modules are loaded by name through `importlib`, so PyInstaller
cannot see them. When you add or rename a step in
[`pipeline.stages.STAGES`](../src/pipeline/stages.py), mirror it in
`PIPELINE_STAGE_HIDDEN_IMPORTS` in
[build_windows_release.py](../packaging/build_windows_release.py).
`tests/test_packaging.py` fails until the two match.

## Explanation

**Why only `dist/release/` is published.** The build also leaves raw PyInstaller
output in `dist/portable/` and `dist/onefile/`; those are intermediates. The
script prunes `dist/release/` to the curated artifacts so a release upload is
always the same two files.

**Why the app shows no version number.** The git tag is the single source of
truth for the release version. Packaging metadata (`pyproject.toml` version,
installer metadata) is kept intentional but is not treated as user-facing
branding.

**What gets bundled.** The PyInstaller command
(`base_pyinstaller_command`) collects the `pipeline` and `gui` packages, the
hidden stage imports above, and three data sets: `gui/icons`,
`config/color_render.csv`, and `config/default_world`. The root `README.md` is
copied next to the portable app. A file the app loads at runtime that is not
in that list is missing from the release even though it works from a checkout.

**CPU only.** The build includes CPU `numba` acceleration for rendering; CUDA is
not required.

## Reference

### Release artifacts

| File | Published |
|---|---|
| `dist/release/Minecraft CityGen-setup.exe` | yes |
| `dist/release/Minecraft CityGen-portable-windows.zip` | yes |
| `dist/release/Minecraft CityGen.exe` | no — only with `--include-standalone`, testing only |
| `dist/store/Minecraft CityGen.msix` | no — only with `--msix`, uploaded to the Microsoft Store |

### Build prerequisites

- Windows; the build script exits on any other OS.
- Build dependencies: `python -m pip install .[build]` (adds PyInstaller).
- [Inno Setup 6](https://jrsoftware.org/isinfo.php): `ISCC.exe` on `PATH` or in
  one of `%LOCALAPPDATA%\Programs\Inno Setup 6\`,
  `%ProgramFiles(x86)%\Inno Setup 6\`, `%ProgramFiles%\Inno Setup 6\`.
- For `--msix` only: `makeappx.exe`, from either the full
  [Windows SDK](https://developer.microsoft.com/windows/downloads/windows-sdk/)
  (on `PATH` or under `%ProgramFiles(x86)%\Windows Kits\10\bin\<version>\x64\`)
  or, much smaller (~22 MB), the
  [Microsoft.Windows.SDK.BuildTools](https://www.nuget.org/packages/Microsoft.Windows.SDK.BuildTools)
  NuGet package: download the `.nupkg`, rename it to `.zip`, and unzip it to
  `%LOCALAPPDATA%\Minecraft CityGen Build\sdk-buildtools\`. No install or admin needed.

### Files

| File | Role |
|---|---|
| [build_windows_release.py](../packaging/build_windows_release.py) | Builds the portable app, zip, installer, optional one-file exe, and optional Store MSIX (`--clean`, `--include-standalone`, `--msix`) |
| [windows_installer.iss](../packaging/windows_installer.iss) | Inno Setup script; receives version and output directory from the build script |
| [AppxManifest.xml](../packaging/AppxManifest.xml) | MSIX manifest template; the build script fills in the Store identity and version |
