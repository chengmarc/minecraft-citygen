# CityGen - Minecraft City Generator

<p align="center">
  <img src="src/gui/icons/app-icon.png" alt="CityGen app icon" width="180">
</p>
<div align="center">
  <h3>
    Download <a href="https://github.com/CDS-SP/minecraft-citygen/releases/download/v0.4.1/CityGen-setup.exe">Windows Installer (.exe)</a> or 
    <a href="https://github.com/CDS-SP/minecraft-citygen/releases/download/v0.4.1/CityGen-portable-windows.zip">Compressed Portable (.zip)</a>
  </h3>
</div>

**Build a full Minecraft city from your own roads and buildings in minutes.**

This project turns a small handcrafted asset set into a complete city layout, preview, and paste-ready in-game result. It is designed for creators who want large-scale city generation without giving up the look and feel of their own Minecraft builds.

## Supported Versions

<p align="center">
  <img src="https://img.shields.io/badge/Minecraft-%E2%89%A5%201.20-4C9A2A" alt="Minecraft >= 1.20">
  <img src="https://img.shields.io/badge/WorldEdit-%E2%89%A5%207.3.0-1E88E5" alt="WorldEdit >= 7.3.0">
</p>

CityGen targets **Minecraft 1.20+** and requires **WorldEdit 7.3.0+** to paste the generated schematics: outputs use the Sponge v3 `.schem` container, which WorldEdit 7.3.0 (the first release for 1.20) introduced and earlier versions cannot read.

> **Note:** WorldEdit 7.3.0's Minecraft coverage depends on the platform — the Bukkit build (Spigot/Paper) supports 1.20–1.20.4, while the Forge build supports 1.20.4 only. Match the WorldEdit build to your server platform and Minecraft version. Verified working on 1.20.4.

## Rendering Result

![Isometric city render 1](docs/isometric1.png)

![Isometric city render 2](docs/isometric2.png)

## In-Game Result

The generated city can be brought back into Minecraft as a real build result:

![In-game city result 1](docs/ingame1.png)

![In-game city result 2](docs/ingame2.png)

![In-game city result 3](docs/ingame3.png)

![In-game city result 4](docs/ingame4.png)

## Built-in Assets

These buildings come with the app by default:

![Built-in Assets](docs/assets.png)

## Desktop Workflow

The app includes extraction tools, previews, and a generation UI built for iteration:

![Desktop UI 1](docs/ui1.png)

![Desktop UI 2](docs/ui2.png)

![Desktop UI 3](docs/ui3.png)

## What It Is

CityGen is a desktop tool that helps you:

- extract roads and building pieces from a Minecraft world
- generate a full city layout from those pieces
- preview the result before committing to it
- export a city you can bring back into Minecraft

It is not a generic block spammer. The goal is to let you define the visual language, then let the tool scale it into a believable city.

## Why It’s Different

- Your assets, not random prefab packs: the generator works from structures you already built.
- Fast visual iteration: you can see city layouts before producing final output.
- In-game ready: the output is meant to become a real Minecraft city, not just concept art.
- Compact workflow: extraction, preview, generation, and render all live in one app.

## Who It’s For

- Minecraft builders who want to scale a build style into a full district or city
- world creators making urban maps faster
- technical builders who want structure without hand-placing every block
- anyone who wants a city generator that still feels handcrafted

## For Technical Details

Refer to [TECHNICAL.md](docs/TECHNICAL.md)
