# Microsoft Store listing — MC CityGen

Everything to paste into Partner Center for MC CityGen, in the submission's order: Properties, Store listings
(English (United States)), Submission options. Pricing and availability, Age ratings and Packages are filled in
Partner Center directly. Images are beside this file (the screenshots in [desktop/](desktop/)), rendered by
`python store-listing/generator/render.py`.

The app and its listing call the game "MC": Mojang's usage guidelines don't allow its name in a product's name,
and the Store has turned down submissions that used it. The name only appears where the guidelines ask for it: the
disclaimer at the end of the description and the trademark credit. The app's name is the one reserved in Partner
Center (`MSIX_DISPLAY_NAME` in [build_windows_release.py](../packaging/build_windows_release.py)).

## Properties

- **Category:** Utilities & tools. **Subcategory:** none.
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

## Store listings — English (United States)

### Description

```
Want a whole MC city, without placing every building by hand?

Build a handful of buildings in your own MC world, mark each one with three blocks, and get back a complete city in their style: avenues and streets, houses along every block, and landmarks spaced through it. Open it as a ready-to-play world, or take the .schem schematic into a world of your own.

Make your first city right away
• Two hand-built asset sets, modern and medieval, come with the app, so your first city needs no building at all.
• A sample world is ready to go: Extract, Preview, Build.

Bring your own buildings
• Mark a building with a gold block and a diamond block at opposite corners, and an emerald block at ground level.
• Stack three marked pieces, and your tower grows taller or shorter to fit the city.
• Modern towers, medieval walls: the city takes the look of whatever you build.

See it before you build it
• Preview the road network and the building layout, and build only when you like what you see.
• Every build gives you a rendered picture of the whole city.

Make it yours
• Five city sizes, from a village to a metropolis.
• Tune road density, avenue and street spacing, turns and T-junctions, and the building mix.
• Roll a new seed for a new city, or keep a seed to make the same city again.

Nothing to sign up for
• Works offline. No account, no ads, no tracking.
• Open source under the Apache 2.0 license.

Requirements and limits
• Windows 10 or 11, 64-bit.
• MC: Java Edition 26.1.2 or later, to play the cities it makes. You don't need it to run the app.
• Your buildings must face south.

NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.
```

### What's new in this version

Rewrite this for each submission; for 2.0.0 (1500 characters or fewer):

```
A new look: the three steps, Extract, Preview and Build, check off as you go, and the progress bar is a strip of ground that grows grass as each step finishes.
• The window is now built on Microsoft Edge WebView2, which comes with Windows 11 and most of Windows 10.
• Each tab's settings and progress sit in one panel below the pictures, which are labelled and zoomable.
• Road and building pieces show on transparent sheets.
• Extract has a Reset, back to the sample world and its areas.
• Your settings, cities and exported worlds carry over.
```

### Product features

One per line in Partner Center ("Add more" for each). Each finishes "With this app, you can …":

```
Grow a whole city from a handful of buildings you make
Get avenues, streets, houses and landmarks laid out for you
Start right away with hand-built modern and medieval asset sets
Use your own buildings, marked with three blocks: gold, diamond and emerald
Have stacked buildings grow taller or shorter to fit the city
Preview the roads and the building layout before you build
Play your city as a ready-to-open world, or take it anywhere as a .schem schematic
See a rendered picture of every city you build
Pick a city size, from a village to a metropolis
Tune road density, street spacing, turns and the building mix
Make the same city again from its seed, or roll a new one
Work offline, with no account, no ads and no tracking
Read and change the code: open source under Apache 2.0
```

### Screenshots

Upload in this order (the first is shown first). Screenshot n shows `docs/pics/promo<n>.png`:

1. `desktop/screenshot-1-promo.png`: the Build tab, a whole modern city from the buildings you make
2. `desktop/screenshot-2-size.png`: the Build tab, a medieval village, from village to metropolis
3. `desktop/screenshot-3-styles.png`: the Build tab, a medieval town, the city taking your buildings' style
4. `desktop/screenshot-4-extract.png`: the Extract tab, your own buildings found in your world and turned into pieces
5. `desktop/screenshot-5-preview.png`: the Preview tab, the road network and building layout before you build

### Store logos

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
- **Short description** (270 characters or fewer):

  ```
  Turn a handful of buildings from your MC world into a whole city: streets, houses and landmarks in your style, or start with the built-in modern and medieval sets. Play it as a world or export a .schem. For Java Edition 26.1.2+. Works offline.
  ```

### Additional information

- **Keywords** (up to 7, 40 characters each, 21 words in all):

  ```
  city generator
  procedural city
  city builder
  schematic generator
  world generator
  medieval town
  Java Edition
  ```

- **Additional system requirements** (each line one item, 200 characters each), under Minimum hardware:

  ```
  MC: Java Edition 26.1.2 or later, to open the worlds it makes. Not needed to run the app.
  ```

- **Copyright and trademark info:**

  ```
  © 2026 chengmarc. Minecraft is a trademark of Mojang Synergies AB.
  ```

- **Additional license terms:**

  ```
  Apache License 2.0: https://github.com/chengmarc/minecraft-citygen/blob/main/LICENSE
  ```

- **Developed by:**

  ```
  chengmarc
  ```

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
