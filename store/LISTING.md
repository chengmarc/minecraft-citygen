# Microsoft Store listing — English (United States)

Everything to paste into Partner Center → MC CityGen → Store listing, in the page's order, then the other fields the
submission asks for. Images are in [listing/](listing/), rendered by `python store/render.py`.

The listing says "MC CityGen", not "Minecraft CityGen": the name reserved in Partner Center
(`MSIX_DISPLAY_NAME` in [build_windows_release.py](../packaging/build_windows_release.py)). Minecraft's usage
guidelines don't allow "Minecraft" in a product's name, and ask for the disclaimer at the end of the description.

## Description

```
Build a whole Minecraft city from a handful of buildings.

MC CityGen takes the roads and buildings you mark up in your own Minecraft world and grows them into a complete city: an avenue and street network, houses along every block, and landmarks spaced through it. The finished city comes out as a world you can open in Minecraft and as a .schem schematic for your own world.

How it works
• Extract: point it at a Minecraft world and choose the road, house and landmark areas on its map.
• Preview: see the road network and the building layout before anything is built.
• Build: get the schematic, a rendered picture of the city, and a playable world.

Your buildings, your style
Mark a building with a gold block and a diamond block at opposite corners, and an emerald block at ground level. Stack three marked pieces and the building grows taller or shorter to fit the city. Modern towers, medieval walls: the city takes the look of whatever you build.

Ready to use
A modern asset set, built by hand block by block, comes with the app, so you can make a city before you build anything.

Tune the city
City size, road density, avenue and street spacing, turns and T-junctions, house style variety and landmark spacing. A seed makes any city again.

Works offline. No account, no ads, no tracking.

Requirements
• Windows 10 or 11, 64-bit
• Minecraft: Java Edition 26.1.2 or later, to play the cities it makes

MC CityGen is open source under the Apache 2.0 license.

NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.
```

## What's new in this version

Leave blank: this is the first submission.

## Product features

One per line in Partner Center ("Add more" for each):

```
Grows a whole city from the buildings you make
Avenues, streets, houses and landmarks, laid out for you
Preview the roads and buildings before you build
Exports a playable world and a .schem schematic
A rendered picture of every city
Mark up your own buildings with three blocks: gold, diamond, emerald
Stackable buildings that grow to fit the city
A hand-built modern asset set included
Tune size, road density, spacing, turns and building mix
Works offline: no account, no ads, no tracking
Open source (Apache 2.0)
```

## Screenshots

Upload in this order (the first is shown first):

1. `listing/screenshot-1-promo.png`: a finished city, as the app renders it
2. `listing/screenshot-2-world.png`: the exported world in Minecraft
3. `listing/screenshot-3-assets.png`: the built-in modern asset set
4. `listing/screenshot-4-markers.png`: marking up your own building
5. `listing/screenshot-5-styles.png`: a medieval city
6. `listing/screenshot-6-app.png`: the Preview tab

## Store logos

| Slot | File |
|---|---|
| 9:16 Poster art (1440 × 2160) | `listing/poster-art-1440x2160.png`: the main logo on Windows 10/11 |
| 1:1 Box art (2160 × 2160) | `listing/box-art-2160.png` |
| 1:1 App tile icon (300 × 300) | `listing/store-logo-300.png` |
| 150 × 150, 71 × 71 | Leave empty; the Store takes them from the package. |

## Trailers, Xbox images

Leave empty.

## Supplemental fields

- **Short title:** leave empty.
- **Voice title:** leave empty.
- **Short description** (270 characters or fewer):

  ```
  Grow a whole Minecraft city from a handful of buildings you mark up in your own world. Preview the roads and layout, then export a playable world and a .schem schematic. For Minecraft: Java Edition 26.1.2+. Works offline.
  ```

## Additional information

- **Keywords** (up to 7, 40 characters each, 21 words in all):

  ```
  city generator
  Minecraft city
  procedural city
  schematic
  Java Edition
  world generator
  city builder
  ```

- **Additional system requirements** (each line one item, 200 characters each):

  Minimum hardware:

  ```
  Minecraft: Java Edition 26.1.2 or later, to open the worlds it makes. Not needed to run the app.
  ```

- **Copyright and trademark info:** `© 2026 chengmarc. Minecraft is a trademark of Mojang Synergies AB.`
- **Additional license terms:** `Apache License 2.0: https://github.com/chengmarc/minecraft-citygen/blob/main/LICENSE`
- **Developed by:** `chengmarc`

## Properties

- **Category:** Utilities & tools. **Subcategory:** none.
- **Privacy policy URL:** `https://github.com/chengmarc/minecraft-citygen/blob/main/PRIVACY.md`
- **Website:** `https://github.com/chengmarc/minecraft-citygen`
- **Support contact info:** `https://github.com/chengmarc/minecraft-citygen/issues`
- **System requirements:** check Mouse under Minimum hardware (areas are chosen on a map). Leave every other row
  unchecked and empty.
- **Product declarations:** none apply. Leave "This product has been tested to meet accessibility guidelines"
  unchecked unless it has been.

## Age ratings

In the questionnaire, none of the parts apply: the app has no user-to-user communication, no generated text, no
purchases, no location sharing and no network access.

## Submission options

- **Restricted capabilities → runFullTrust:**

  ```
  MC CityGen is a desktop app built with Python and Qt (PyInstaller), packaged with the Desktop Bridge. runFullTrust is required for any packaged Win32 desktop app to launch its executable (EntryPoint="Windows.FullTrustApplication"). It is used only to run the app itself. The app does not access the network; it reads the Minecraft world folder the user chooses and writes its outputs to its own app data folder.
  ```

- **Notes for certification:**

  ```
  No account, sign-in, internet connection or Minecraft install is needed. The app comes with a sample world already selected, with its road, house and landmark areas chosen. Click Extract and wait for it to finish, then the Preview tab's Preview button, then the Build tab's Build button. Build shows a rendered picture of the finished city; Copy World opens the folder with the exported world.
  ```
