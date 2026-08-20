#!/usr/bin/env python
"""Regenerate the renderer block-color lookup CSV from a downloaded Minecraft client JAR.

This is a maintenance script. The app still ships only ``src/engine/color_render.csv``;
the generator itself is not part of the packaged runtime.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
DEFAULT_OUTPUT = ROOT / "src" / "engine" / "color_render.csv"
VERSION_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
HTTP_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class Face:
    texture_path: str
    x1: float
    x2: float
    z1: float
    z2: float
    y: float
    uv: tuple[float, float, float, float]
    rotation: int
    order: int


class MinecraftTopColorExtractor:
    def __init__(self, jar_path: Path) -> None:
        self.jar_path = jar_path
        self.zf = zipfile.ZipFile(jar_path)
        self.json_cache: dict[str, dict] = {}
        self.model_cache: dict[str, dict] = {}
        self.texture_cache: dict[str, tuple[Image.Image, tuple[int, int]]] = {}

    def load_json(self, path: str) -> dict:
        if path not in self.json_cache:
            self.json_cache[path] = json.loads(self.zf.read(path))
        return self.json_cache[path]

    def normalize_model_ref(self, ref: str) -> str:
        if ref.startswith("minecraft:"):
            ref = ref.split(":", 1)[1]
        if not ref.startswith(("block/", "item/")):
            ref = f"block/{ref}"
        return f"assets/minecraft/models/{ref}.json"

    def merge_model(self, model_path: str) -> dict:
        if model_path in self.model_cache:
            return self.model_cache[model_path]

        data = self.load_json(model_path)
        merged = {"textures": {}, "elements": None}

        parent = data.get("parent")
        if parent:
            parent_model = self.merge_model(self.normalize_model_ref(parent))
            merged["textures"].update(parent_model.get("textures", {}))
            if parent_model.get("elements") is not None:
                merged["elements"] = parent_model["elements"]

        merged["textures"].update(data.get("textures", {}))
        if "elements" in data:
            merged["elements"] = data["elements"]

        self.model_cache[model_path] = merged
        return merged

    def resolve_texture_ref(self, value: object, textures: dict[str, object]) -> str | None:
        seen: set[str] = set()
        while isinstance(value, str) and (value.startswith("#") or value in textures):
            key = value[1:] if value.startswith("#") else value
            if key in seen:
                return None
            seen.add(key)
            value = textures.get(key)

        if isinstance(value, dict):
            value = value.get("sprite")

        if not isinstance(value, str) or not value:
            return None
        if value.startswith("minecraft:"):
            value = value.split(":", 1)[1]
        return f"assets/minecraft/textures/{value}.png"

    def load_texture(self, texture_path: str) -> tuple[Image.Image, tuple[int, int]]:
        if texture_path in self.texture_cache:
            return self.texture_cache[texture_path]

        with self.zf.open(texture_path) as fh:
            img = Image.open(fh).convert("RGBA")
            width, height = img.size
            frame_height = width if height >= width and height % width == 0 else height
            first_frame = img.crop((0, 0, width, frame_height))

        result = (first_frame, first_frame.size)
        self.texture_cache[texture_path] = result
        return result

    def representative_models(self, blockstate_path: str) -> list[str]:
        data = self.load_json(blockstate_path)

        if "variants" in data:
            key = "" if "" in data["variants"] else next(iter(data["variants"]))
            choice = data["variants"][key]
            if isinstance(choice, list):
                choice = choice[0]
            return [choice["model"]]

        if "multipart" in data:
            models: list[str] = []
            for part in data["multipart"]:
                apply = part["apply"]
                if isinstance(apply, list):
                    apply = apply[0]
                models.append(apply["model"])
            return models

        return []

    def default_up_uv(self, element: dict) -> tuple[float, float, float, float]:
        from_x, _, from_z = element["from"]
        to_x, _, to_z = element["to"]
        return (from_x, from_z, to_x, to_z)

    def collect_faces(self, block_name: str) -> list[Face]:
        blockstate_path = f"assets/minecraft/blockstates/{block_name}.json"
        faces: list[Face] = []
        order = 0

        for model_ref in self.representative_models(blockstate_path):
            try:
                model = self.merge_model(self.normalize_model_ref(model_ref))
            except KeyError:
                continue

            textures = model.get("textures", {})
            for element in model.get("elements") or []:
                face = element.get("faces", {}).get("up")
                if not face:
                    continue

                texture_path = self.resolve_texture_ref(face.get("texture"), textures)
                if not texture_path:
                    continue

                x1, _, z1 = element["from"]
                x2, y2, z2 = element["to"]
                if x1 == x2 or z1 == z2:
                    continue

                faces.append(
                    Face(
                        texture_path=texture_path,
                        x1=min(x1, x2),
                        x2=max(x1, x2),
                        z1=min(z1, z2),
                        z2=max(z1, z2),
                        y=y2,
                        uv=tuple(face.get("uv", self.default_up_uv(element))),
                        rotation=int(face.get("rotation", 0)) % 360,
                        order=order,
                    )
                )
                order += 1

        faces.sort(key=lambda item: (item.y, item.order), reverse=True)
        return faces

    def collect_texture_paths(self, block_name: str) -> list[str]:
        blockstate_path = f"assets/minecraft/blockstates/{block_name}.json"
        texture_paths: list[str] = []
        seen: set[str] = set()

        for model_ref in self.representative_models(blockstate_path):
            try:
                model = self.merge_model(self.normalize_model_ref(model_ref))
            except KeyError:
                continue

            textures = model.get("textures", {})
            for element in model.get("elements") or []:
                for face in (element.get("faces") or {}).values():
                    texture_path = self.resolve_texture_ref(face.get("texture"), textures)
                    if texture_path and texture_path not in seen:
                        seen.add(texture_path)
                        texture_paths.append(texture_path)

            for texture_ref in textures.values():
                texture_path = self.resolve_texture_ref(texture_ref, textures)
                if texture_path and texture_path not in seen:
                    seen.add(texture_path)
                    texture_paths.append(texture_path)

        return texture_paths

    def sample_face(self, face: Face, px: int, pz: int) -> tuple[int, int, int, int] | None:
        center_x = px + 0.5
        center_z = pz + 0.5
        if not (face.x1 <= center_x < face.x2 and face.z1 <= center_z < face.z2):
            return None

        width = face.x2 - face.x1
        depth = face.z2 - face.z1
        u_frac = (center_x - face.x1) / width
        v_frac = (center_z - face.z1) / depth

        if face.rotation == 90:
            u_frac, v_frac = 1.0 - v_frac, u_frac
        elif face.rotation == 180:
            u_frac, v_frac = 1.0 - u_frac, 1.0 - v_frac
        elif face.rotation == 270:
            u_frac, v_frac = v_frac, 1.0 - u_frac

        u1, v1, u2, v2 = face.uv
        u = u1 + (u2 - u1) * u_frac
        v = v1 + (v2 - v1) * v_frac

        try:
            image, (img_w, img_h) = self.load_texture(face.texture_path)
        except KeyError:
            return None
        tex_x = min(img_w - 1, max(0, math.floor(u / 16.0 * img_w)))
        tex_y = min(img_h - 1, max(0, math.floor(v / 16.0 * img_h)))
        return image.getpixel((tex_x, tex_y))

    def average_texture_color(self, texture_paths: list[str]) -> tuple[int, int, int] | None:
        totals = [0, 0, 0]
        count = 0

        for texture_path in texture_paths:
            try:
                image, (width, height) = self.load_texture(texture_path)
            except KeyError:
                continue
            pixels = image.load()
            for y in range(height):
                for x in range(width):
                    r, g, b, a = pixels[x, y]
                    if a == 0:
                        continue
                    totals[0] += r
                    totals[1] += g
                    totals[2] += b
                    count += 1

        if not count:
            return None

        return tuple(round(total / count) for total in totals)

    def average_block_color(self, block_name: str) -> tuple[int, int, int] | None:
        faces = self.collect_faces(block_name)
        pixels: list[tuple[int, int, int]] = []
        if faces:
            for pz in range(16):
                for px in range(16):
                    for face in faces:
                        rgba = self.sample_face(face, px, pz)
                        if rgba is None or rgba[3] == 0:
                            continue
                        pixels.append(rgba[:3])
                        break

        if pixels:
            count = len(pixels)
            return tuple(round(sum(channel[i] for channel in pixels) / count) for i in range(3))

        return self.average_texture_color(self.collect_texture_paths(block_name))

    def extract(self) -> list[tuple[str, int, int, int]]:
        rows: list[tuple[str, int, int, int]] = []
        for name in sorted(self.zf.namelist()):
            if not name.startswith("assets/minecraft/blockstates/") or not name.endswith(".json"):
                continue
            block_name = Path(name).stem
            if not block_name:
                continue
            color = self.average_block_color(block_name)
            if color is None:
                continue
            rows.append((f"minecraft:{block_name}", *color))
        return rows


def load_json_url(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "CityGen render palette updater"})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.load(response)


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_version_metadata(version: str | None) -> tuple[str, dict]:
    manifest = load_json_url(VERSION_MANIFEST_URL)
    version_id = version or manifest["latest"]["release"]
    for item in manifest["versions"]:
        if item.get("id") == version_id:
            return version_id, item
    raise SystemExit(f"Minecraft version not found in manifest: {version_id}")


def download_client_jar(version: str | None) -> tuple[str, Path]:
    version_id, version_metadata = resolve_version_metadata(version)
    version_manifest = load_json_url(version_metadata["url"])
    client = version_manifest.get("downloads", {}).get("client")
    if not client:
        raise SystemExit(f"Minecraft version {version_id} does not expose a client download.")

    download_url = client["url"]
    expected_sha1 = client.get("sha1")
    jar_path = TOOLS_DIR / f"minecraft-client-{version_id}.jar"
    temp_path = jar_path.with_suffix(".jar.part")
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)

    if jar_path.is_file() and expected_sha1 and sha1_file(jar_path) == expected_sha1:
        return version_id, jar_path

    request = urllib.request.Request(download_url, headers={"User-Agent": "CityGen render palette updater"})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        with temp_path.open("wb") as fh:
            shutil.copyfileobj(response, fh)

    if expected_sha1:
        digest = sha1_file(temp_path)
        if digest != expected_sha1:
            temp_path.unlink(missing_ok=True)
            raise SystemExit(
                f"Downloaded client JAR SHA-1 mismatch for {version_id}: expected {expected_sha1}, got {digest}"
            )

    temp_path.replace(jar_path)
    return version_id, jar_path


def write_csv(rows: list[tuple[str, int, int, int]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["block_name", "r", "g", "b"])
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download a Minecraft client JAR and regenerate src/engine/color_render.csv."
    )
    parser.add_argument(
        "--version",
        help="Minecraft version id to download. Defaults to the latest release in Mojang's manifest.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output CSV path. Defaults to {DEFAULT_OUTPUT}.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = args.output.expanduser().resolve()
    version_id, jar_path = download_client_jar(args.version)

    extractor = MinecraftTopColorExtractor(jar_path)
    rows = extractor.extract()
    write_csv(rows, output_path)
    print(f"downloaded {version_id} client JAR to {jar_path}")
    print(f"wrote {len(rows)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
