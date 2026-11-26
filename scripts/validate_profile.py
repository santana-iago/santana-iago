#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from itertools import product
from pathlib import Path
from urllib.parse import urlparse

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "assets" / "generated"
ERRORS: list[str] = []
WARNINGS: list[str] = []


def error(message: str) -> None:
    ERRORS.append(message)


def warn(message: str) -> None:
    WARNINGS.append(message)


def main() -> int:
    profile_path = ROOT / "profile.yml"
    if not profile_path.exists():
        error("profile.yml is missing")
        profile = {}
    else:
        profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))

    for section in ("contacts", "featured", "current", "certifications"):
        for item in profile.get(section, []):
            asset = item.get("icon") or item.get("logo")
            if asset and not (ROOT / asset).exists():
                error(f"Missing asset referenced by {section}: {asset}")
            url = item.get("url")
            if url and urlparse(url).scheme not in {"http", "https", "mailto"}:
                error(f"Unsupported URL scheme: {url}")

    required = [ROOT / "README.md"]
    for theme in ("light", "dark"):
        required += [
            ROOT / f"docs/preview-desktop-{theme}.png",
            ROOT / f"docs/preview-mobile-{theme}.png",
        ]
    picture_names = ["hero", "status", "featured-header", "current-header"]
    picture_names += [f'contact-{item["label"].lower()}' for item in profile.get("contacts", [])]
    picture_names += [f"featured-card-{i}" for i, _ in enumerate(profile.get("featured", []))]
    picture_names += [item.get("generated_name", f"current-{i}") for i, item in enumerate(profile.get("current", []))]
    if profile.get("certifications"):
        picture_names += ["certifications-header"] + [f"cert-{i}" for i, _ in enumerate(profile["certifications"])]
    if profile.get("statistics"):
        picture_names.append("statistics-header")
    for name, layout, theme in product(picture_names + ["featured"], ("desktop", "mobile"), ("light", "dark")):
        required.append(GENERATED / f"{name}-{layout}-{theme}.svg")
    for path in required:
        if not path.exists():
            error(f"Required file is missing: {path.relative_to(ROOT)}")

    for svg in GENERATED.glob("*.svg"):
        try:
            ET.parse(svg)
        except ET.ParseError as exc:
            error(f"Invalid SVG {svg.relative_to(ROOT)}: {exc}")

    if profile.get("statistics"):
        stats_path = ROOT / profile["statistics"]["path"]
        if not stats_path.exists():
            error(f"Missing statistics asset: {stats_path.relative_to(ROOT)}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").exists() else ""
    for reference in re.findall(r'(?:src|srcset)="(\./[^\"]+)"', readme):
        local = ROOT / urlparse(reference).path
        if not local.exists():
            error(f"README references missing file: {reference}")

    if "generated-v" in readme:
        error("README references a legacy versioned generated directory")
    if not profile.get("certifications") and ("certifications-header" in readme or "## Certifications I'm pursuing" in readme):
        error("README includes certifications although the section is disabled")
    if not profile.get("statistics") and ("statistics-header" in readme or "profile-summary-card-output/" in readme):
        error("README includes profile statistics although the section is disabled")
    for name, theme in product(picture_names, ("light", "dark")):
        fragment = f"#gh-{theme}-mode-only"
        desktop = re.escape(f"./assets/generated/{name}-desktop-{theme}.svg{fragment}")
        mobile = re.escape(f"./assets/generated/{name}-mobile-{theme}.svg{fragment}")
        pattern = (
            rf'<a (?:href="{fragment}" tabindex="-1"|href="(?:https?://|mailto:)[^"\n]+{fragment}")><picture>'
            rf'<source media="\(min-width: \d+px\)" srcset="{desktop}">'
            rf'<img src="{mobile}" alt="[^"\n]*"></picture></a>'
        )
        if not re.search(pattern, readme):
            error(f"Missing matching desktop and mobile sources for {name} in the {theme} theme")

    if "prefers-color-scheme" in readme:
        error("README must leave color selection to GitHub's theme fragments")
    for svg in GENERATED.glob("*.svg"):
        content = svg.read_text(encoding="utf-8")
        if "prefers-color-scheme" in content:
            error(f"Generated SVG must have a fixed palette: {svg.relative_to(ROOT)}")

    legacy = [p for p in (ROOT / "assets").glob("generated-v*") if p.is_dir()]
    if legacy:
        error("Legacy generated directories remain: " + ", ".join(str(p.relative_to(ROOT)) for p in legacy))
    if (ROOT / "assets/hidden.svg").exists():
        error("Obsolete assets/hidden.svg remains")

    BRAND_ASSET_MAX_BYTES = 40_000
    for asset in (ROOT / "assets/brands").glob("*"):
        if not asset.is_file():
            continue
        if asset.suffix.lower() not in {".svg", ".png"}:
            error(f"Brand asset must be SVG or PNG: {asset.relative_to(ROOT)}")
            continue
        if asset.suffix.lower() == ".png":
            try:
                with Image.open(asset) as image:
                    image.verify()
            except OSError as exc:
                error(f"Invalid brand image {asset.relative_to(ROOT)}: {exc}")
        size = asset.stat().st_size
        if size > BRAND_ASSET_MAX_BYTES:
            error(
                f"Brand asset too large ({size // 1024} KB): {asset.relative_to(ROOT)} "
                f"— likely an unresized raster image embedded in the SVG wrapper. "
                f"Downscale the source image to roughly 3x its display size before re-embedding."
            )

    for png in (ROOT / "docs").glob("*.png"):
        try:
            with Image.open(png) as image:
                if image.width < 300:
                    warn(f"Preview is unusually narrow: {png.relative_to(ROOT)}")
        except Exception as exc:
            error(f"Unable to open preview {png.relative_to(ROOT)}: {exc}")

    for message in WARNINGS:
        print(f"WARNING: {message}")
    for message in ERRORS:
        print(f"ERROR: {message}", file=sys.stderr)
    if ERRORS:
        return 1
    print("Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
