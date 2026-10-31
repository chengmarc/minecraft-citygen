# MC CityGen 2.1.0 Release Notes

Released on October 31, 2026.

MC CityGen 2.1.0 speaks eight languages: Deutsch, English, Español, Français,
Português (Brasil), Русский, 简体中文 and 日本語. The same seeds still make the
same cities.

## Highlights

- **Eight languages.** The app starts in the system's language if it has it,
  else English. A picker at the right of the header changes it at once, keeping
  the pictures and any run under way, and the app remembers the choice.
- **The Store listing in every language.** Each language has its own text and
  images, with screenshots of the app in that language.

## What Changed

### GUI

- The app's description is "Modular City Generator", was "Procedural City
  Generator".

### Store listing

- The text is one file per language in `store-listing/localization/`, and what's
  entered once for a submission is in `store-listing/SUBMISSION.md`, was
  `store-listing/LISTING.md`.
- The images are rendered into `dist/<code>/`, one folder per language, was
  tracked in `store-listing/`. Git keeps only the README's three screenshots, in
  `docs/screenshots/`.
- `store-listing/generator/render.py` also makes `docs/app-icon.png`.

## Upgrade Notes

- Nothing to do: saved settings carry over. The first launch follows the
  system's language until one is picked in the header.
- Publish only `MC CityGen-setup.exe` to GitHub. Upload `MC CityGen.msix` to
  Partner Center, not to GitHub.

## Verification

- `python -m pytest -q`
- `python packaging/build_windows_release.py --clean --msix`
- `python store-listing/generator/render.py`
