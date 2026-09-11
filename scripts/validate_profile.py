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

    # (readme_path, generated_dir) pairs to validate — English at the
    # repository root, plus each localization the build produces (currently
    # just pt-BR). Keeping this list explicit means a future language is
    # caught here too as soon as it's wired into build_profile.LANGUAGES.
    LOCALES = [
        (ROOT / "README.md", GENERATED),
        (ROOT / "README.pt-BR.md", GENERATED / "pt-BR"),
    ]

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

    if not (ROOT / "profile.pt-BR.yml").exists():
        error("profile.pt-BR.yml is missing")

    for readme_path, generated_dir in LOCALES:
        for svg in generated_dir.rglob("*.svg"):
            try:
                ET.parse(svg)
            except ET.ParseError as exc:
                error(f"Invalid SVG {svg.relative_to(ROOT)}: {exc}")

    stats_path = ROOT / profile.get("statistics", {}).get("path", "")
    if not stats_path.exists():
        error(f"Missing statistics asset: {stats_path.relative_to(ROOT) if stats_path != ROOT else 'path'}")

    for readme_path, generated_dir in LOCALES:
        if not readme_path.exists():
            continue  # already reported above as a required/missing file
        readme = readme_path.read_text(encoding="utf-8")

        for reference in re.findall(r'(?:src|srcset)="(\./[^\"]+)"', readme):
            local = ROOT / reference.removeprefix("./")
            if not local.exists():
                error(f"{readme_path.name} references missing file: {reference}")

        if "generated-v" in readme:
            error(f"{readme_path.name} references a legacy versioned generated directory")
        for name in ("hero", "status", "current-header", "certifications-header", "statistics-header"):
            if f"{name}-mobile.svg" not in readme or f"{name}-desktop.svg" not in readme:
                error(f"{readme_path.name} is missing an explicit mobile/desktop <picture> source for {name}")
        if "featured-header-mobile.svg" not in readme or "featured-header-desktop.svg" not in readme:
            error(f"{readme_path.name} is missing an explicit mobile/desktop <picture> source for featured-header")
        for index in range(len(profile.get("featured", []))):
            if f"featured-card-{index}-mobile.svg" not in readme or f"featured-card-{index}-desktop.svg" not in readme:
                error(f"{readme_path.name} is missing an explicit mobile/desktop <picture> source for featured-card-{index}")

        # GitHub wraps README <picture> elements in its own theme-switching custom
        # element, which (confirmed against a live page) does not reliably honour a
        # <source media="..."> that combines a width bound with prefers-color-scheme
        # — it must never reappear in the generated markup. Theme instead lives
        # inside each SVG file as a native prefers-color-scheme media query, which
        # the browser evaluates itself while rendering the image.
        if "prefers-color-scheme" in readme:
            error(f"{readme_path.name} <picture> markup must not combine width and prefers-color-scheme in the same source")
        if not generated_dir.exists():
            continue
        for svg in generated_dir.rglob("*.svg"):
            content = svg.read_text(encoding="utf-8")
            if "prefers-color-scheme" not in content:
                error(f"Generated SVG is missing an embedded prefers-color-scheme rule: {svg.relative_to(ROOT)}")

    # Language selector: EN links to PT-BR, PT-BR links to EN, each with its
    # own language marked non-clickable. Regression-proofs the one hand-authored
    # piece of markup build_profile.py emits (LANGUAGE_SELECTOR in that file).
    en_readme = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").exists() else ""
    pt_readme = (ROOT / "README.pt-BR.md").read_text(encoding="utf-8") if (ROOT / "README.pt-BR.md").exists() else ""
    if en_readme:
        if '<a href="./README.pt-BR.md">' not in en_readme:
            error("README.md is missing a working link to README.pt-BR.md in its language selector")
        if "<strong><kbd>EN</kbd></strong>" not in en_readme:
            error("README.md language selector does not mark EN as the active language")
    if pt_readme:
        if '<a href="./README.md">' not in pt_readme:
            error("README.pt-BR.md is missing a working link to README.md in its language selector")
        if "<strong><kbd>PT-BR</kbd></strong>" not in pt_readme:
            error("README.pt-BR.md language selector does not mark PT-BR as the active language")

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
