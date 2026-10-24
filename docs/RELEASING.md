# Releasing — Windows builds

How the source tree becomes the two end-user deliverables — a Windows installer
for GitHub Releases and an MSIX package for the Microsoft Store — built by
[packaging/](../packaging). Nothing in `packaging/` ships inside the app.

← Back to the [source architecture overview](../src/README.md).

## How-to guides

### Cut a release

1. Freeze the scope. Do not mix feature work into the release build pass.
2. Choose the release tag. The git tag is the release version of record; bump
   the other places that spell the version out to match:
   - `version` in [pyproject.toml](../pyproject.toml) — the build script
     passes it to the installer as `AppVersion`
   - nothing in the root [README.md](../README.md): its download badge
     carries no version and links to `releases/latest`
3. Update [CHANGELOG.md](CHANGELOG.md) with the release date and
   the final changes, and add `docs/release-notes/RELEASE_NOTES_<version>.md`.
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

6. Confirm `dist/` holds only the installer
   (see [release artifacts](#release-artifacts)).
7. Install the installer on a non-dev machine or a clean VM and smoke-test the
   real user flow:
   - first launch succeeds, with no unexpected dependency prompts
   - the Extract tab accepts a world path and extraction completes
   - Preview completes
   - Build completes: city `.schem`, isometric render, and exported world
   - generated files land in the expected `appdata/` folders; the exported
     world appears under `appdata/05_world/saves/` and "Copy World" opens it
   - the exported world loads in MC with the player standing on the city
   - uninstall works cleanly
8. Tag the release in git only after the installer has been verified.
9. Publish the installer as the GitHub release.

### Build a standalone exe for testing

```bash
python packaging/build_windows_release.py --clean --include-standalone
```

This additionally writes `dist/MC CityGen.exe`. It is for
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

   This additionally writes `dist/MC CityGen.msix`.
3. Smoke-test the packaged app before uploading. With Developer Mode on,
   register the unpacked layout instead of installing the unsigned MSIX:

   ```powershell
   Add-AppxPackage -Register "build\release\msix\AppxManifest.xml"
   ```

   Run the same checks as the installer smoke test. Generated files should land
   under `%LOCALAPPDATA%\Packages\<package family name>\LocalCache\Local\MC CityGen\`,
   and the saves folder should open in Explorer. Remove it afterwards with
   `Get-AppxPackage chengmarc.167357377D6E6 | Remove-AppxPackage`.
4. Upload the `.msix` in a new Partner Center submission. If the app's look or
   the pictures in `docs/pics/` changed, re-render the listing images first
   (below).

### Fill in the Partner Center submission

[`store-listing/LISTING.md`](../store-listing/LISTING.md) has every field to paste, in Partner
Center's order: the description, features, keywords, system requirements, the
wording for the `runFullTrust` restricted capability and the notes for
certification. Its images are beside it: the logos in `store-listing/`, the
screenshots in `store-listing/desktop/`.

### Re-render the listing images

```bash
python store-listing/generator/render.py
```

It redraws `store-listing/` with Microsoft Edge in headless mode, from
`store-listing/generator/logo.html` (box art, poster art, tile icon) and `store-listing/generator/shots.html` (the
screenshots). The screenshots put a caption beside a picture from `docs/pics/`;
change the captions or pictures in `shots.html`, and the matching claims in
`LISTING.md` with them.

### Update the README pictures

No script makes `docs/pics/`; each picture was chosen and copied in by hand.

| Pictures | Where they came from |
|---|---|
| `assets_*.png`, `assets_*.gif` | the builds stage: `appdata/02_builds/renders/_contact_sheet.png` and `appdata/02_builds/buildings.gif` |
| `modern_iso.png`, `medieval_iso.png` | the city stage: `appdata/04_city/renders/seed_<n>.png` |
| `ingame*.png`, `base.png` | in-game screenshots |
| `promo*.png` | the app's window on its Build tab |
| `type1.png`, `type2.png` | in-game screenshots, annotated with the marker blocks |

The current renders can't be remade: their seeds, the medieval set's
extraction regions, and the asset sheets' 1440 px layout were never recorded.
When you next replace them, write `scripts/update_readme_pics.py` to run those
stages with fixed settings and copy the results here, then list the copied files in
`.gitattributes` under it. If `promo*.png` or `base.png` change, re-render the
listing images too (above).

### Keep the build in step with a new pipeline step

Stage step modules are loaded by name through `importlib`, so PyInstaller
cannot see them. When you add or rename a step in
[`pipeline.stages.STAGES`](../src/pipeline/stages.py), mirror it in
`PIPELINE_STAGE_HIDDEN_IMPORTS` in
[build_windows_release.py](../packaging/build_windows_release.py).
`tests/test_packaging.py` fails until the two match.

## Explanation

**Why only `dist/` is published.** `dist/` holds only what ships. Everything
on the way (PyInstaller's app folder and work files in `build/packaging/portable/`
and `build/packaging/onefile/`, the MSIX layout, the rendered icons) stays in
`build/packaging/`, and the script removes a standalone exe an earlier build
left in `dist/`, so a release upload is always the one installer.

**Why the app shows no version number.** The git tag is the single source of
truth for the release version. Packaging metadata (`pyproject.toml` version,
installer metadata) is kept intentional but is not treated as user-facing
branding.

**What gets bundled.** The PyInstaller command
(`base_pyinstaller_command`) collects the `pipeline` and `gui` packages, the
hidden stage imports above, and five data sets: the page in `gui/static`
(its icons included), `config/color_render.csv`, `config/default_world`, the window icon,
`app-icon.ico`, and `app-icon.svg`, which the page shows as its brand. The root `README.md` is copied next to the app. A file the app loads at runtime that is not
in that list is missing from the release even though it works from a checkout.

**One icon source.** `src/app-icon.svg` is the only icon in the repo. The build
renders it to `build/packaging/app-icon.png` with headless Microsoft Edge, then
makes the Store package logos and `app-icon.ico` from that PNG; the `.ico` is
both the installer's icon and the bundled window icon. It uses Edge because most
SVG renderers ignore the clip path that rounds the tile and the blur filters.
From a checkout, `python packaging/build_windows_release.py --icon-only` makes
just the PNG and the `.ico`, which the app then uses as its window icon.

**CPU only.** The build includes CPU `numba` acceleration for rendering; CUDA is
not required.

## Reference

### Release artifacts

| File | Published |
|---|---|
| `dist/MC CityGen-setup.exe` | yes |
| `dist/MC CityGen.exe` | no — only with `--include-standalone`, testing only |
| `dist/MC CityGen.msix` | no — only with `--msix`, uploaded to the Microsoft Store |

### Build prerequisites

- Windows; the build script exits on any other OS.
- Build dependencies: `python -m pip install .[build]` (adds PyInstaller).
- Microsoft Edge, which comes with Windows: it renders the app icon.
- [Inno Setup 6](https://jrsoftware.org/isinfo.php): `ISCC.exe` on `PATH` or in
  one of `%LOCALAPPDATA%\Programs\Inno Setup 6\`,
  `%ProgramFiles(x86)%\Inno Setup 6\`, `%ProgramFiles%\Inno Setup 6\`.
- For `--msix` only: `makeappx.exe`, from either the full
  [Windows SDK](https://developer.microsoft.com/windows/downloads/windows-sdk/)
  (on `PATH` or under `%ProgramFiles(x86)%\Windows Kits\10\bin\<version>\x64\`)
  or, much smaller (~22 MB), the
  [Microsoft.Windows.SDK.BuildTools](https://www.nuget.org/packages/Microsoft.Windows.SDK.BuildTools)
  NuGet package: download the `.nupkg`, rename it to `.zip`, and unzip it to
  `%LOCALAPPDATA%\MC CityGen Build\sdk-buildtools\`. No install or admin needed.

### Files

| File | Role |
|---|---|
| [build_windows_release.py](../packaging/build_windows_release.py) | Builds the app folder, the installer, an optional one-file exe, and the optional Store MSIX (`--clean`, `--include-standalone`, `--msix`) |
| [windows_installer.iss](../packaging/windows_installer.iss) | Inno Setup script; receives version and output directory from the build script |
| [AppxManifest.xml](../packaging/AppxManifest.xml) | MSIX manifest template; the build script fills in the Store identity and version |
| [store-listing/LISTING.md](../store-listing/LISTING.md) | The Store listing's text, field by field |
| [store-listing/PRIVACY.md](../store-listing/PRIVACY.md) | The privacy policy; its GitHub address is the listing's privacy policy URL |
| [store-listing/generator/render.py](../store-listing/generator/render.py) | Renders the listing's images into `store-listing/` |
