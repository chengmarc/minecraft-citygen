# Minecraft CityGen 1.2.1 Release Notes

Released on September 28, 2026.

Minecraft CityGen 1.2.1 is a packaging release that brings the app to the
Microsoft Store as **MC CityGen**. It also fixes how the installed app picks
the folder it writes to, and ships a new app icon. City generation and its
output are unchanged.

## Highlights

- **Microsoft Store build.** The Store rejected the unsigned Inno Setup
  installer under policy 10.2.9, which requires Win32 installers to be
  code-signed. The app is now also packaged as an MSIX, which the Store signs
  itself. The GitHub installer and portable zip are still available.
- **Writable-folder fix.** The app keeps its artifacts next to the exe when
  that folder is writable, and in `%LOCALAPPDATA%\Minecraft CityGen` otherwise.
  The check used `os.access`, which on Windows ignores folder permissions and so
  reported Program Files as writable. It now tests by writing a real temp file.
- **New app icon.**

## What Changed

### Packaging

- `python packaging/build_windows_release.py --msix` also writes
  `dist/store/Minecraft CityGen.msix` from the portable build, using
  `packaging/AppxManifest.xml`. It needs `makeappx.exe`, from either the full
  Windows SDK or the ~22 MB `Microsoft.Windows.SDK.BuildTools` NuGet package.
- The MSIX version is the release version with a `.0` added (`1.2.1.0`).

### App data location

- In the Store build, generated files live in
  `%LOCALAPPDATA%\Packages\chengmarc.MCCityGen_v8ssbrv406ypg\LocalCache\Local\Minecraft CityGen\`.
  Windows would redirect writes there anyway. Writing to that path directly
  means the saves folder opens in Explorer, and uninstalling the Store app
  removes the data.

### Documentation

- `docs/RELEASING.md` covers building the Store package, testing it locally
  with `Add-AppxPackage -Register`, and uploading it.
- README badges are now local SVGs.

## Upgrade Notes

- Installer and portable users: nothing changes. Existing artifacts stay where
  they were.
- The Store app keeps its own data and does not see artifacts from an installer
  or portable copy.
- Publish the curated artifacts to GitHub:
  `Minecraft CityGen-setup.exe` and `Minecraft CityGen-portable-windows.zip`.
  Upload `Minecraft CityGen.msix` to Partner Center, not to GitHub.

## Verification

- `python -m pytest -q`
- `python packaging/build_windows_release.py --clean --msix`
- Registered the MSIX layout locally, ran Extract → Preview → Build, and
  confirmed the saves folder opens in Explorer.
