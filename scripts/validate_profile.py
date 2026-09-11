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
        ]
    for layout in ("desktop", "mobile"):
        required += [
            GENERATED / f"hero-{layout}.svg",
            GENERATED / f"status-{layout}.svg",
            GENERATED / f"featured-{layout}.svg",
            GENERATED / f"current-header-{layout}.svg",
            GENERATED / f"contact-linkedin-{layout}.svg",
            GENERATED / f"current-0-{layout}.svg",
            GENERATED / f"cert-0-{layout}.svg",
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
    for name in ("hero", "status", "current-header", "certifications-header", "statistics-header"):
        if f"{name}-mobile.svg" not in readme or f"{name}-desktop.svg" not in readme:
            error(f"README is missing an explicit mobile/desktop <picture> source for {name}")
    if "featured-header-mobile.svg" not in readme or "featured-header-desktop.svg" not in readme:
        error("README is missing an explicit mobile/desktop <picture> source for featured-header")
    for index in range(len(profile.get("featured", []))):
        if f"featured-card-{index}-mobile.svg" not in readme or f"featured-card-{index}-desktop.svg" not in readme:
            error(f"README is missing an explicit mobile/desktop <picture> source for featured-card-{index}")

    # GitHub wraps README <picture> elements in its own theme-switching custom
    # element, which (confirmed against a live page) does not reliably honour a
    # <source media="..."> that combines a width bound with prefers-color-scheme
    # — it must never reappear in the generated markup. Theme instead lives
    # inside each SVG file as a native prefers-color-scheme media query, which
    # the browser evaluates itself while rendering the image.
    if "prefers-color-scheme" in readme:
        error("README <picture> markup must not combine width and prefers-color-scheme in the same source")
    for svg in GENERATED.glob("*.svg"):
        content = svg.read_text(encoding="utf-8")
        if "prefers-color-scheme" not in content:
            error(f"Generated SVG is missing an embedded prefers-color-scheme rule: {svg.relative_to(ROOT)}")

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
