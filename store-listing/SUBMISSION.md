# Microsoft Store submission — MC CityGen

How to fill in a Partner Center submission for MC CityGen, in its order: Properties, Store listings, Submission
options. What's entered once for the product or the submission is here, to paste. What's entered per language is that
language's Store listing: its text in `localization/<code>.md`, and its images in `dist/<code>/`. Pricing
and availability, Age ratings and Packages are filled in Partner Center directly. The images are made by
`python store-listing/generator/render.py`, and only the README's three English screenshots, in `docs/screenshots/`, are kept in git.

The app and its listing call the game "MC": Mojang's usage guidelines don't allow its name in a product's name,
and the Store has turned down submissions that used it. The name only appears where the guidelines ask for it: the
disclaimer at the end of the description and the trademark credit. The app's name is the one reserved in Partner
Center (`MSIX_DISPLAY_NAME` in [build_windows_release.py](../packaging/build_windows_release.py)).

## Properties

- **Category:** Multimedia design. **Subcategory:** Kids + family.
- **Privacy policy:** paste the whole of [PRIVACY.md](PRIVACY.md) as it is; it is plain text written for the box.
- **Website:**

  ```
  https://github.com/chengmarc/minecraft-citygen
  ```

- **Support contact info:**

  ```
  https://github.com/chengmarc/minecraft-citygen/issues
  ```

- **System requirements:** check Mouse under Minimum hardware (areas are chosen on a map). Leave every other row
  unchecked and empty.
- **Product declarations:** none apply. Leave "This product has been tested to meet accessibility guidelines"
  unchecked unless it has been.

## Store listings

One per language, each filled in the same way. Each language in the package needs a listing, or
removing under Add/remove languages.

### Text

The fields in `localization/<code>.md`, within Partner Center's limits, which
`tests/test_packaging.py` checks:

- **Description:** keep its closing disclaimer in English, as it is in each file. Don't use the game's name
  outside that disclaimer and the trademark credit: see the note at the top.
- **What's new in this version** (1500 characters or fewer): rewrite this for each submission, in every file.
- **Product features:** one per line in Partner Center ("Add more" for each). Each finishes "With this app,
  you can …".
- **Short description** (270 characters or fewer), under Supplemental fields.
- **Keywords** (up to 7, 40 characters each, 21 words in all), under Additional information.
- **Additional system requirements** (each line one item, 200 characters each), under Additional information,
  Minimum hardware.
- **Copyright and trademark info**, **Additional license terms** and **Developed by**, under Additional
  information: the same in every language.

### Screenshots

From `dist/<code>/`, in this order (the first is shown first). Each shows the app's window in that
language, on the cities in `generator/scenes.json`:

1. `screenshot-1-promo.png`: the Build tab, a whole modern city from the buildings you make
2. `screenshot-2-size.png`: the Build tab, a medieval village, from village to metropolis
3. `screenshot-3-styles.png`: the Build tab, a medieval town, the city taking your buildings' style
4. `screenshot-4-extract.png`: the Extract tab, your own buildings found in your world and turned into pieces
5. `screenshot-5-preview.png`: the Preview tab, the road network and building layout before you build

### Store logos

From `dist/<code>/`. The tile has no words, so it's the same in every language.

| Slot | File |
|---|---|
| 9:16 Poster art (1440 × 2160) | `poster-art-1440x2160.png`: the main logo on Windows 10/11 |
| 1:1 Box art (2160 × 2160) | `box-art-2160.png` |
| 1:1 App tile icon (300 × 300) | `store-logo-300.png` |
| 150 × 150, 71 × 71 | Leave empty; the Store takes them from the package. |

### Trailers, Xbox images

Leave empty.

### Supplemental fields

- **Short title:** leave empty; the name is short.
- **Voice title:** leave empty.

### Filling them in

Export listing and Import listings in Partner Center take all the languages at once, as a `.csv` and a folder. Its
`default` column fills any language left blank, so the shared fields only need entering there.

## Submission options

- **Publishing hold options:** publish as soon as it passes certification, unless a release is being timed for a
  weekend or a game update, when MC players are most active.
- **Restricted capabilities → runFullTrust:**

  ```
  MC CityGen is a desktop app built with Python and a WebView2 window (PyInstaller), packaged with the Desktop Bridge. runFullTrust is required for any packaged Win32 desktop app to launch its executable (EntryPoint="Windows.FullTrustApplication"). It is used only to run the app itself. The app does not access the internet: its window shows a page served by the app itself on 127.0.0.1. It reads the MC world folder the user chooses and writes its outputs to its own app data folder.
  ```

- **Notes for certification:**

  ```
  No account, sign-in, internet connection or MC install is needed. The app opens with a sample world already selected, with its road, house and landmark areas chosen. On the Extract tab, click Extract and wait for it to finish. On the Preview tab, click Preview to see the road network and building layout. On the Build tab, click Build: it shows a rendered picture of the finished city. Worlds then opens the folder with the exported world.
  ```
