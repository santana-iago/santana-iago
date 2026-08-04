#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
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
            GENERATED / f"hero-desktop-{theme}.svg",
            GENERATED / f"hero-mobile-{theme}.svg",
            GENERATED / f"status-desktop-{theme}.svg",
            GENERATED / f"status-mobile-{theme}.svg",
            GENERATED / f"featured-desktop-{theme}.svg",
            GENERATED / f"featured-mobile-{theme}.svg",
            GENERATED / f"current-header-desktop-{theme}.svg",
            GENERATED / f"current-header-mobile-{theme}.svg",
            GENERATED / f"contact-linkedin-desktop-{theme}.svg",
            GENERATED / f"contact-linkedin-mobile-{theme}.svg",
            GENERATED / f"current-0-desktop-{theme}.svg",
            GENERATED / f"current-0-mobile-{theme}.svg",
            GENERATED / f"cert-0-desktop-{theme}.svg",
            GENERATED / f"cert-0-mobile-{theme}.svg",
        ]
    for path in required:
        if not path.exists():
            error(f"Required file is missing: {path.relative_to(ROOT)}")

    for svg in GENERATED.glob("*.svg"):
        try:
            ET.parse(svg)
        except ET.ParseError as exc:
            error(f"Invalid SVG {svg.relative_to(ROOT)}: {exc}")

    stats_path = ROOT / profile.get("statistics", {}).get("path", "")
    if not stats_path.exists():
        error(f"Missing statistics asset: {stats_path.relative_to(ROOT) if stats_path != ROOT else 'path'}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").exists() else ""
    for reference in re.findall(r'(?:src|srcset)="(\./[^\"]+)"', readme):
        local = ROOT / reference.removeprefix("./")
        if not local.exists():
            error(f"README references missing file: {reference}")

    if "generated-v" in readme:
        error("README references a legacy versioned generated directory")
    for name in ("hero", "status", "featured", "current-header", "certifications-header", "statistics-header"):
        if f"{name}-mobile-dark.svg" not in readme:
            error(f"README is missing explicit mobile dark source for {name}")

    legacy = [p for p in (ROOT / "assets").glob("generated-v*") if p.is_dir()]
    if legacy:
        error("Legacy generated directories remain: " + ", ".join(str(p.relative_to(ROOT)) for p in legacy))
    if (ROOT / "assets/hidden.svg").exists():
        error("Obsolete assets/hidden.svg remains")

    BRAND_ASSET_MAX_BYTES = 40_000
    for asset in (ROOT / "assets/brands").glob("*"):
        if not asset.is_file():
            continue
        if asset.suffix.lower() != ".svg":
            error(f"Brand asset must be SVG: {asset.relative_to(ROOT)}")
            continue
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
