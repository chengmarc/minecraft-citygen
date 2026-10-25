<div align="center">

  <img src="src/app-icon.svg" width="180"><br>

  <a href="https://github.com/chengmarc/minecraft-citygen/releases/latest/download/MC.CityGen-setup.exe"><img src="docs/badges/badge-download.svg" height="50"></a>
  <a href="https://apps.microsoft.com/detail/9NPSMX3TB1T7"><img src="docs/badges/badge-microsoft-store.svg" height="50"></a>
  <img src="docs/badges/badge-mc.svg" height="50">

  <h1>MC CityGen - Procedural City Generator</h1>
  
  <img src="store-listing/desktop/screenshot-1-promo.png">
  <img src="store-listing/desktop/screenshot-3-styles.png">

</div>

## Generated Cities

<table>
  <tr><th width="50%">Modern City</th><th width="50%">Medieval City</th></tr>
  <tr>
    <td valign="bottom" align="center"><img src="docs/pics/modern_iso.png" width="100%"></td>
    <td valign="bottom" align="center"><img src="docs/pics/medieval_iso.png" width="100%"></td>
  </tr>
  <tr>
    <td><img src="docs/pics/ingame1.png" width="100%"></td>
    <td><img src="docs/pics/ingame3.png" width="100%"></td>
  </tr>
  <tr>
    <td><img src="docs/pics/ingame2.png" width="100%"></td>
    <td><img src="docs/pics/ingame4.png" width="100%"></td>
  </tr>
</table>

# Built-in Assets

## Modern Assets

<img src="docs/pics/assets_modern.png" alt="Modern built-in asset sheet" width="100%">

## Medieval Assets

<img src="docs/pics/assets_medieval.png" alt="Medieval built-in asset sheet" width="100%">

# Tutorial - Marking Your Own Assets

### Your buildings must face south

**MC CityGen** builds cities from structures you mark up inside your own MC world,
using a handful of marker blocks.

For buildings, place: 
- a **Gold block** and a **Diamond block** at two opposite corners of each region you want captured.
- an **Emerald block** horizontally adjacent to the bottom gold block to mark the authored ground level. 

## One-piece building & three-piece building
- One gold/diamond pair creates a one-piece building.
- Three vertically aligned pairs with the same footprint create a stackable building with bottom, middle, and top pieces. 
- You can tune any three-piece building with a sign directive above its emerald: `stack: 3-7` — how many middle sections it may grow (min–max)

<img src="docs/pics/type1.png" alt="One-layer build marker convention" width="100%">

<img src="docs/pics/type2.png" alt="Three-layer build marker convention" width="100%">

The exact rules for roads and buildings are in the
[in-world asset conventions](src/README.md#in-world-asset-conventions).

# Technical Details

```bash
python -m pip install -e .
python -m pytest -q
pythonw src/application.pyw
```

The source is one package, `src/citygen/`; its guide is [src/README.md](src/README.md). Releases follow the
[release guide](docs/RELEASING.md).