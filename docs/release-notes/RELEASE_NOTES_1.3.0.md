# MC CityGen 1.3.0 Release Notes

Released on October 14, 2026.

MC CityGen 1.3.0 renames the app from Minecraft CityGen to **MC CityGen** and
gives it a new look built around its new icon. The bundled world gains a
medieval building set and five more landmarks, renders use more vivid colours,
and a second extraction in the same session now actually uses the new
buildings. The portable zip is retired: GitHub Releases has the installer, and
the Microsoft Store has the MSIX.

## Highlights

- **MC CityGen.** The app, its installer, its data folder and its docs now use
  the name MC CityGen, and call the game MC.
- **A medieval set.** The bundled world has a medieval building set and five
  more landmarks, and the default extraction areas cover them.
- **A new look.** A new app icon, and a window themed after it: a sky-blue tab
  row and title bar, grass-green buttons, a dirt-brown progress bar, a sky
  behind the renders, and a blue selection on the world map.
- **Re-extraction fix.** Building pieces were cached by file name for the life
  of the app, so extracting again in the same session built cities from the
  previous extraction's buildings. Pieces are now re-read whenever the file
  changes.

## What Changed

### GUI and rendering

- The window's colours follow the icon's layers: sky at the top, grass for the
  things you act on, dirt at the bottom. On Windows 11 the title bar takes the
  sky colour too.
- The render viewer paints a sky gradient that stays put while you zoom and
  drag the image.
- Renders use a more saturated copy of each block's colour: the new `vivid_*`
  columns of `color_render.csv`. Texture averages came out dull; muted colours
  such as dirt, wood and grass gain the most, and grays stay gray.

### Bundled world and exported worlds

- The bundled world has the medieval set and five more landmarks, and the
  default building areas are larger to include them.
- The bundled world and every exported city show the app icon in MC's world
  list.

### Packaging

- The release is the installer, `MC CityGen-setup.exe`; there is no portable
  zip any more. The Store package is `MC CityGen.msix`.
- The app icon has one source, `src/app-icon.svg`. The build renders it with
  headless Microsoft Edge and makes the installer icon, the Store logos and the
  window icon from that render, so Edge is now a build prerequisite.
- The Python package is `mc-city-generator`.

### Documentation

- The Microsoft Store listing, its privacy policy and the script that renders
  its images live in `store/`.
- New README pictures, and new Store screenshots.

## Upgrade Notes

- The installer keeps the same app id, so it upgrades a 1.2.x install in place,
  into the existing install folder. The old `Minecraft CityGen.exe` and its
  shortcuts may stay beside the new ones; uninstall 1.2.x first for a clean
  install.
- When the install folder isn't writable, settings and outputs now live in
  `%LOCALAPPDATA%\MC CityGen`. A previous `%LOCALAPPDATA%\Minecraft CityGen`
  folder is left in place; copy anything you want to keep from it.
- Saved settings from 0.1.0 are no longer carried over; the form starts from
  its defaults. Settings saved by 1.x load as before.
- Cities rendered with 1.3.0 look more saturated than the same seed rendered
  with 1.2.x. Layouts and exported worlds are unaffected.
- Publish only `MC CityGen-setup.exe` to GitHub. Upload `MC CityGen.msix` to
  Partner Center, not to GitHub.

## Verification

- `python -m pytest -q`
- `python packaging/build_windows_release.py --clean --msix`
