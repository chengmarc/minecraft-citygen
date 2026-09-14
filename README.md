<div align="center">
  <h1>Minecraft CityGen - Customizable City Generator</h1>
  <img src="src/gui/icons/app-icon.svg" alt="Minecraft CityGen app icon" width="180">
  <br><br>
  <img src="https://img.shields.io/badge/Version-1.1.0-6495ED?style=for-the-badge&amp;logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0id2hpdGUiIGZpbGwtcnVsZT0iZXZlbm9kZCIgZD0iTTMgM2g4bDEwIDEwLTggOEwzIDExWk04LjUgN2ExLjUgMS41IDAgMSAwLTMgMCAxLjUgMS41IDAgMCAwIDMgMFoiLz48L3N2Zz4%3D" alt="Release 1.1.0">
  <!-- Minecraft badge logo: Pictogrammers Material Design Icons (Apache-2.0), https://github.com/Templarian/MaterialDesign/blob/master/svg/minecraft.svg -->
  <img src="https://img.shields.io/badge/Minecraft-%E2%89%A5%2026.1.2-4C9A2A?style=for-the-badge&amp;logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0id2hpdGUiIGQ9Ik00LDJIMjBBMiwyIDAgMCwxIDIyLDRWMjBBMiwyIDAgMCwxIDIwLDIySDRBMiwyIDAgMCwxIDIsMjBWNEEyLDIgMCAwLDEgNCwyTTYsNlYxMEgxMFYxMkg4VjE4SDEwVjE2SDE0VjE4SDE2VjEySDE0VjEwSDE4VjZIMTRWMTBIMTBWNkg2WiIvPjwvc3ZnPg%3D%3D" alt="Minecraft >= 26.1.2">
  <h3>
    Download <a href="https://github.com/doubletrends/minecraft-citygen/releases/download/v1.1.0/Minecraft CityGen-setup.exe">Windows Installer (.exe)</a> or
    <a href="https://github.com/doubletrends/minecraft-citygen/releases/download/v1.1.0/Minecraft CityGen-portable-windows.zip">Compressed Portable (.zip)</a>
  </h3>
  <br>
</div>

**Build a TheoTown style Minecraft city from your own roads and buildings in minutes.**

This project turns a small handcrafted asset set into a complete city layout, preview, and paste-ready in-game result. It is designed for creators who want large-scale city generation without giving up the look and feel of their own Minecraft builds.

# Rendering Result

<table>
  <tr><th>Modern City</th><th>Medieval City</th></tr>
  <tr>
    <td valign="bottom" align="center"><img src="docs/pics/modern.gif" alt="Modern City" width="100%"></td>
    <td valign="bottom" align="center"><img src="docs/pics/medieval.gif" alt="Medieval City" width="100%"></td>
  </tr>
</table>

# In-Game Result

| Modern City| Medieval City |
| --- | --- |
| <img src="docs/pics/ingame1.png" alt="Modern City" width="100%"> | <img src="docs/pics/ingame3.png" alt="Medieval City" width="100%"> | 
| <img src="docs/pics/ingame2.png" alt="Modern City" width="100%"> | <img src="docs/pics/ingame4.png" alt="Medieval City" width="100%"> | 

# Built-in Assets (Modern + Medieval)

| Assets Overview | Individual Asset |
| --- | --- |
| <img src="docs/pics/assets_modern.png" alt="Modern built-in asset sheet" width="100%"> | <img src="docs/pics/assets_modern.gif" alt="Modern built-in assets animated preview" width="100%"> | 
| <img src="docs/pics/assets_medieval.png" alt="Medieval built-in asset sheet" width="100%"> | <img src="docs/pics/assets_medieval.gif" alt="Medieval built-in assets animated preview" width="100%"> | 

# User Interface

| Extraction | Preview & Generation |
| --- | --- |
| <img src="docs/pics/ui1.png" alt="UI Image 1" width="100%"> | <img src="docs/pics/ui2.png" alt="UI Image 2" width="100%"> |

# Tutorial - Marking Your Own Assets

**Minecraft CityGen** builds cities from structures you mark up inside your own Minecraft world,
using a handful of marker blocks.

For buildings, place: 
- a **Gold block** and a **Diamond block** at two opposite corners of each region you want captured.
- an **Emerald block** horizontally adjacent to the bottom gold block to mark the authored ground level. 

One gold/diamond pair creates a one-piece building. Three vertically aligned pairs
with the same footprint create a stackable building with bottom, middle, and top
pieces. A sign above the emerald can set stack options.

You can tune any three-piece building with a sign directive above its emerald: `stack: 3-7` — how many middle sections it may grow (min–max)

<img src="docs/pics/type1.png" alt="Unstackable Builds" width="100%">

<img src="docs/pics/type2.png" alt="Stackable Builds" width="100%">

# For Technical Details

See the [source architecture overview](src/README.md) and its per-package guides
([config](src/config/README.md), [engine](src/engine/README.md),
[gui](src/gui/README.md), [pipeline](src/pipeline/README.md)).

## Developer Quick Start

```bash
python -m pip install -e .
pytest -q
pythonw application.pyw
```

The source tree is organized as four packages under `src/`: `config`, `engine`,
`gui`, and `pipeline`. Generated previews, schematics, renders, exported worlds,
test caches, and packaging outputs live in git-ignored directories such as
`artifacts/`, `build/`, `dist/`, and `.pytest_cache/`.

Pipeline stages can be run through the stage registry in a checkout, for example:

```bash
python src/pipeline/stages.py city --seed 5
```

Use `MC_CITY_*` environment overrides through `pipeline.services` for in-process
runs; the pipeline runtime applies them under a lock and reloads import-time
configuration safely for one run at a time.

### Supported Minecraft Versions

![26.1.2](https://img.shields.io/badge/26.1.2-404040)
![26.2](https://img.shields.io/badge/26.2-404040)
