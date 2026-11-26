#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import html
import io
import shutil
from itertools import product
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag

import cairosvg
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "assets" / "generated"
MOBILE_WIDTH = 336
RASTER_EMBED_MAX_SIZE = 144
# Some mobile WebViews use a 980px layout viewport before applying zoom.
DESKTOP_BREAKPOINT = 1024
DOCS = ROOT / "docs"

THEMES = {
    "light": {
        "text": "#1f2328",
        "muted": "#57606a",
        "label": "#656d76",
        "line": "#d0d7de",
        "soft_line": "#eaeef2",
        "card": "#f6f8fa",
        "card_border": "#d0d7de",
        "icon_disc": "#ffffff",
        "arrow": "#656d76",
        "preview_bg": "#ffffff",
    },
    "dark": {
        "text": "#f0f6fc",
        "muted": "#9aa4b2",
        "label": "#8b949e",
        "line": "#30363d",
        "soft_line": "#21262d",
        "card": "#161b22",
        "card_border": "#30363d",
        "icon_disc": "#161b22",
        "arrow": "#8b949e",
        "preview_bg": "#0d1117",
    },
}


def load_profile() -> dict[str, Any]:
    return yaml.safe_load((ROOT / "profile.yml").read_text(encoding="utf-8"))


def esc(value: str) -> str:
    return html.escape(str(value), quote=True)


def data_uri(relative: str, theme: str) -> str:
    path = ROOT / relative
    if theme == "dark":
        candidate = path.with_name(f"{path.stem}-dark{path.suffix}")
        if candidate.exists():
            path = candidate
    if path.suffix.lower() == ".svg":
        raw_text = path.read_text(encoding="utf-8")
        if "<image" not in raw_text:
            # Real vector artwork (not one of the brand marks, which are already a
            # raster wrapped in an <image>): rasterize it so it's embedded the same
            # proven way as everything else. A real vector SVG nested two levels
            # deep (data-uri SVG inside a data-uri SVG inside an <img>) with its own
            # prefers-color-scheme rule isn't reliably themed by real browsers —
            # confirmed live: the email/GitHub icons vanished in light mode despite
            # rendering correctly wherever this project uses a plain raster nested
            # image instead.
            png_bytes = cairosvg.svg2png(bytestring=raw_text.encode("utf-8"), output_width=144)
            return f"data:image/png;base64,{base64.b64encode(png_bytes).decode('ascii')}"
    raw = path.read_bytes()
    if path.suffix.lower() == ".png":
        with Image.open(io.BytesIO(raw)) as source:
            if max(source.size) > RASTER_EMBED_MAX_SIZE:
                # Project marks render at roughly 44px. Keep about 3x that
                # resolution for dense displays without embedding the full source.
                artwork = source.convert("RGBA")
                artwork.thumbnail((RASTER_EMBED_MAX_SIZE, RASTER_EMBED_MAX_SIZE), Image.Resampling.LANCZOS)
                with io.BytesIO() as compact:
                    artwork.save(compact, format="PNG", optimize=True)
                    raw = compact.getvalue()
    mime = {
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(path.suffix.lower())
    if not mime:
        raise ValueError(f"Unsupported asset type: {path}")
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _theme_rules(c: dict[str, str]) -> str:
    return f"""
.surface{{fill:{c['preview_bg']}}}
.card-bg{{fill:{c['card']}}}
.card-border{{stroke:{c['card_border']}}}
.line{{stroke:{c['line']}}}
.soft-line{{stroke:{c['soft_line']}}}
.icon-disc{{fill:{c['icon_disc']};stroke:{c['card_border']}}}
.arrow{{stroke:{c['arrow']};fill:{c['arrow']}}}
.hero-headline{{font:italic 600 34px Georgia,'Times New Roman',serif;fill:{c['text']}}}
.hero-headline-mobile{{font:italic 600 21px Georgia,'Times New Roman',serif;letter-spacing:-.1px;fill:{c['text']}}}
.hero-copy{{font:400 13px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;fill:{c['muted']}}}
.hero-copy-mobile{{font:400 13px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;letter-spacing:-.08px;fill:{c['muted']}}}
.status-label{{font:600 9px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:1.4px;fill:{c['label']}}}
.status-value{{font:500 13px ui-monospace,SFMono-Regular,Menlo,monospace;fill:{c['text']}}}
.status-value-mobile{{font:500 13.5px ui-monospace,SFMono-Regular,Menlo,monospace;fill:{c['text']}}}
.contact-label{{font:600 9px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:1.45px;fill:{c['label']}}}
.contact-value{{font:600 13px ui-monospace,SFMono-Regular,Menlo,monospace;fill:{c['text']}}}
.contact-value-mobile{{font:600 13.5px ui-monospace,SFMono-Regular,Menlo,monospace;fill:{c['text']}}}
.ui{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;fill:{c['text']}}}
.section{{font-size:15px;font-weight:500;letter-spacing:-.1px}}
.section-mobile{{font-size:18px;font-weight:600;letter-spacing:-.2px}}
.title{{font-size:14px;font-weight:700;letter-spacing:-.1px}}
.title-mobile{{font-size:17px;font-weight:700;letter-spacing:-.12px}}
.current-title{{font-size:14px;font-weight:700;letter-spacing:-.1px}}
.category{{font:700 10px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;letter-spacing:1.2px;fill:{c['label']}}}
.category-mobile{{font:700 11px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;letter-spacing:.8px;fill:{c['label']}}}
.description{{font-size:11.3px;font-weight:400;fill:{c['muted']}}}
.description-mobile{{font-size:14.5px;font-weight:400;fill:{c['muted']}}}
.cert-title{{font-size:15px;font-weight:700;letter-spacing:-.12px}}
.cert-title-mobile{{font-size:15.5px;font-weight:700;letter-spacing:-.12px}}
.cert-subtitle{{font-size:10.5px;font-weight:400;fill:{c['muted']}}}
.cert-subtitle-mobile{{font-size:11px;font-weight:400;fill:{c['muted']}}}
.cert-status{{font:700 7.4px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;letter-spacing:1.4px;fill:{c['label']}}}
"""


def svg_open(width: int, height: int, theme: str, *, surface: bool = True) -> list[str]:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<style>{_theme_rules(THEMES[theme])}</style>',
    ]
    if surface:
        parts.append(f'<rect class="surface" width="{width}" height="{height}"/>')
    return parts


def svg_close(parts: list[str]) -> str:
    parts.append("</svg>")
    return "".join(parts)


def add_text(parts: list[str], x: float, y: float, value: str, cls: str, anchor: str | None = None) -> None:
    anchor_attr = f' text-anchor="{anchor}"' if anchor else ""
    parts.append(f'<text x="{x}" y="{y}" class="{cls}"{anchor_attr}>{esc(value)}</text>')


def add_multiline(parts: list[str], x: float, y: float, lines: list[str], cls: str, line_height: float) -> None:
    parts.append(f'<text x="{x}" y="{y}" class="{cls}">')
    for i, line in enumerate(lines):
        parts.append(f'<tspan x="{x}" dy="{0 if i == 0 else line_height}">{esc(line)}</tspan>')
    parts.append("</text>")


def add_image(parts: list[str], x: float, y: float, width: float, height: float, relative: str, theme: str) -> None:
    attrs = f'x="{x}" y="{y}" width="{width}" height="{height}" preserveAspectRatio="xMidYMid meet"'
    parts.append(f'<image href="{data_uri(relative, theme)}" {attrs}/>')


def add_line(parts: list[str], x1: float, y1: float, x2: float, y2: float, soft: bool = False) -> None:
    parts.append(f'<line class="{"soft-line" if soft else "line"}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>')


def add_arrow(parts: list[str], x: float, y: float) -> None:
    parts.append(
        f'<path d="M{x-4} {y+4} L{x+4} {y-4} M{x-1} {y-4} H{x+4} V{y+1}" '
        'fill="none" class="arrow" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def wrap_words(value: str, max_chars: int, max_lines: int | None = None) -> list[str]:
    words = value.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if current and len(candidate) > max_chars:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .") + "…"
    return lines or [""]


def section_header(parts: list[str], title: str, width: int, mobile: bool) -> None:
    left = 16 if mobile else 2
    right = width - (16 if mobile else 2)
    add_text(parts, left, 27 if mobile else 22, title, "ui section-mobile" if mobile else "ui section")
    add_line(parts, left, 43 if mobile else 35, right, 43 if mobile else 35)


def generate_hero(profile: dict[str, Any], mobile: bool, theme: str) -> str:
    # Both lines are rendered in fonts that GitHub's real renderer substitutes per-OS
    # (e.g. Consolas/Courier New on Windows for the monospace stack, or a wider
    # Georgia fallback for the headline) — measurably wider than what the font used
    # to preview this locally. Font sizes carry a real safety margin (calibrated
    # from an actual overflow seen in a browser, not a local render), and both
    # lines wrap defensively instead of relying on an exact single-line fit.
    meta = profile["meta"]
    if mobile:
        width = MOBILE_WIDTH
        headline_line_height, copy_line_height = 25, 18
        headline_lines = wrap_words(meta["headline"], max_chars=25)
        copy_lines = wrap_words(meta["introduction"], max_chars=36)
        headline_y = 32
        copy_y = headline_y + headline_line_height * (len(headline_lines) - 1) + 23
        bottom_y = copy_y + copy_line_height * (len(copy_lines) - 1) + 16
        height = bottom_y + 5
        parts = svg_open(width, height, theme)
        add_line(parts, 16, 4, width - 16, 4)
        add_multiline(parts, 16, headline_y, headline_lines, "hero-headline-mobile", headline_line_height)
        add_multiline(parts, 16, copy_y, copy_lines, "hero-copy-mobile", copy_line_height)
        add_line(parts, 16, bottom_y, width - 16, bottom_y)
        return svg_close(parts)
    width = 880
    headline_line_height, copy_line_height = 34, 16
    headline_lines = wrap_words(meta["headline"], max_chars=50, max_lines=2)
    copy_lines = wrap_words(meta["introduction"], max_chars=90, max_lines=2)
    headline_y = 58
    copy_y = headline_y + headline_line_height * (len(headline_lines) - 1) + 34
    bottom_y = copy_y + copy_line_height * (len(copy_lines) - 1) + 22
    height = bottom_y + 9
    parts = svg_open(width, height, theme)
    add_line(parts, 2, 8, 878, 8)
    add_multiline(parts, 2, headline_y, headline_lines, "hero-headline", headline_line_height)
    add_multiline(parts, 4, copy_y, copy_lines, "hero-copy", copy_line_height)
    add_line(parts, 2, bottom_y, 878, bottom_y)
    return svg_close(parts)


def generate_status(profile: dict[str, Any], mobile: bool, theme: str) -> str:
    items = profile["status"]
    if mobile:
        width, height = MOBILE_WIDTH, 188
        parts = svg_open(width, height, theme)
        add_line(parts, 16, 2, width - 16, 2)
        for i, item in enumerate(items):
            y = 13 + i * 60
            add_text(parts, 16, y + 13, item["label"], "status-label")
            add_text(parts, 16, y + 39, item["value"], "status-value-mobile")
            add_line(parts, 16, y + 51, width - 16, y + 51)
        return svg_close(parts)
    width, height = 880, 72
    parts = svg_open(width, height, theme)
    add_line(parts, 0, .5, 880, .5)
    for x in (294, 587):
        add_line(parts, x, 16, x, 56)
    xs = (12, 318, 611)
    for x, item in zip(xs, items):
        add_text(parts, x, 28, item["label"], "status-label")
        add_text(parts, x, 49, item["value"], "status-value")
    add_line(parts, 0, 71.5, 880, 71.5)
    return svg_close(parts)


def generate_contact_card(item: dict[str, Any], mobile: bool, theme: str) -> str:
    # Desktop is narrower than before (280 -> 265) so 3 cards reliably share one
    # row without an HTML width attribute (see responsive_picture). The
    # value wraps defensively instead of assuming it always fits one line.
    width, height = (MOBILE_WIDTH, 78) if mobile else (265, 76)
    parts = svg_open(width, height, theme, surface=False)
    parts.append(f'<rect class="card-bg card-border" x=".5" y=".5" width="{width-1}" height="{height-1}" rx="10"/>')
    cy = height / 2
    label = item["label"].upper()
    if label == "LINKEDIN":
        parts.append(f'<rect x="20" y="{cy-14}" width="28" height="28" rx="7" fill="#0A66C2"/>')
        parts.append(f'<text x="27" y="{cy+6}" font-family="Arial" font-size="16" font-weight="700" fill="#ffffff">in</text>')
    else:
        parts.append(f'<rect class="icon-disc" x="20" y="{cy-14}" width="28" height="28" rx="7"/>')
        add_image(parts, 26, cy-8, 16, 16, item["icon"], theme)
    add_text(parts, 60, cy-9, label, "contact-label")
    value_cls = "contact-value-mobile" if mobile else "contact-value"
    value_lines = wrap_words(item["value"], max_chars=30 if mobile else 22, max_lines=2)
    if len(value_lines) == 1:
        add_text(parts, 60, cy+14, value_lines[0], value_cls)
    else:
        add_multiline(parts, 60, cy+8, value_lines, value_cls, 14)
    add_arrow(parts, width-20, cy)
    return svg_close(parts)


def generate_featured(profile: dict[str, Any], mobile: bool, theme: str) -> str:
    items = profile["featured"]
    if mobile:
        rows = [mobile_project_row(item, theme) for item in items]
        y = 53
        parts = svg_open(MOBILE_WIDTH, y + sum(height for height, _ in rows), theme)
        section_header(parts, "featured work", MOBILE_WIDTH, True)
        for height, row in rows:
            parts.append(f'<g transform="translate(0 {y})">')
            parts.extend(row)
            parts.append('</g>')
            y += height
        return svg_close(parts)
    width, height = 880, 232
    parts = svg_open(width, height, theme)
    section_header(parts, "featured work", width, False)
    gap = 24
    col_w = (880 - 2 * gap) / 3
    top = 54
    for i, item in enumerate(items):
        x = i * (col_w + gap)
        if i:
            add_line(parts, x - gap/2, 54, x - gap/2, 218, True)
        add_image(parts, x + 8, top + 10, item["logo_width"], item["logo_height"], item["logo"], theme)
        add_multiline(parts, x + 72, top + 20, item["title_lines"], "ui title", 18)
        category_lines = item.get("category_lines", [item["category"]])
        add_multiline(parts, x + 72, top + 62, category_lines, "category", 11)
        add_multiline(parts, x + 8, top + 91 + 11 * (len(category_lines) - 1), wrap_words(item["description"], int(item.get("description_max_chars", 38)), int(item.get("description_max_lines", 3))), "ui description", 17)
        if item.get("url"):
            add_arrow(parts, x + col_w - 20, top + 18)
        add_line(parts, x, 218, x + col_w, 218)
    return svg_close(parts)


def mobile_project_row(item: dict[str, Any], theme: str) -> tuple[int, list[str]]:
    parts: list[str] = []
    title_lines = item.get("title_lines") or wrap_words(item["title"], 26)
    category_lines = wrap_words(item["category"], 40)
    description_lines = wrap_words(item["description"], 40)
    title_y = 37 if len(title_lines) == 1 else 28
    category_y = max(69, title_y + 20 * (len(title_lines) - 1) + 21)
    description_y = category_y + 14 * (len(category_lines) - 1) + 23
    bottom = description_y + 20 * (len(description_lines) - 1) + 18
    logo_width = item.get("logo_width_mobile", 49)
    logo_height = item.get("logo_height_mobile", 42)
    add_image(parts, 16, 11, logo_width, logo_height, item["logo"], theme)
    add_multiline(parts, 76, title_y, title_lines, "ui title-mobile", 20)
    add_multiline(parts, 16, category_y, category_lines, "category-mobile", 14)
    add_multiline(parts, 16, description_y, description_lines, "ui description-mobile", 20)
    if item.get("url"):
        add_arrow(parts, MOBILE_WIDTH - 20, 24)
    add_line(parts, 16, bottom, MOBILE_WIDTH - 16, bottom)
    return bottom + 6, parts


def generate_featured_card(item: dict[str, Any], index: int, mobile: bool, theme: str) -> str:
    """Render one featured-work card so it can be wrapped in its own link."""
    if mobile:
        height, row = mobile_project_row(item, theme)
        return svg_close(svg_open(MOBILE_WIDTH, height, theme) + row)

    col_w = (880 - 48) / 3
    # Keep all three linked images on one line in GitHub's rendered README.
    # Separators remain inside the first two cards, so the row still reads as a
    # three-column layout without relying on extra inline-image width.
    width = col_w
    height = 164
    parts = svg_open(width, height, theme)
    add_image(parts, 8, 10, item["logo_width"], item["logo_height"], item["logo"], theme)
    add_multiline(parts, 72, 20, item["title_lines"], "ui title", 18)
    category_lines = item.get("category_lines", [item["category"]])
    add_multiline(parts, 72, 62, category_lines, "category", 11)
    add_multiline(parts, 8, 91 + 11 * (len(category_lines) - 1), wrap_words(item["description"], int(item.get("description_max_chars", 38)), int(item.get("description_max_lines", 3))), "ui description", 17)
    if item.get("url"):
        add_arrow(parts, width - 20, 18)
    add_line(parts, 0, height, col_w, height)
    if index < 2:
        add_line(parts, width - 1, 0, width - 1, height, True)
    return svg_close(parts)


def _current_title_lines_desktop(item: dict[str, Any]) -> list[str]:
    return item.get("title_lines_desktop") or wrap_words(item["title"], 39, 2)


def _current_description_lines_desktop(item: dict[str, Any]) -> list[str]:
    return wrap_words(item["description"], 38, item.get("description_max_lines", 3))


def generate_current_card(
    item: dict[str, Any],
    mobile: bool,
    theme: str,
    index: int = 0,
    total: int = 0,
    row_title_lines: int = 1,
    row_description_lines: int = 1,
) -> str:
    if mobile:
        height, row = mobile_project_row(item, theme)
        return svg_close(svg_open(MOBILE_WIDTH, height, theme) + row)
    # Desktop is narrower than before (425 -> 390) so 2 cards reliably share a
    # row without an HTML width attribute (see responsive_picture). The
    # description now wraps across up to 3 (tighter) lines instead of 2 wider
    # ones, so per-line width doesn't have to shrink as much. Category and
    # description position/height are both computed from actual line counts
    # rather than assumed to always be 1 and 3 lines respectively.
    width = 390
    title_lines = _current_title_lines_desktop(item)
    title_y = 31 if len(title_lines) == 1 else 23
    # A 2-line title needs the same clearance below its second line that a
    # 1-line title has below its only line (23px, from title_y=31 to
    # category_y=54) — otherwise the category tag crowds the title's second
    # line instead of the card growing to make room for it. row_title_lines
    # (the max title-line count across both cards sharing this row) keeps
    # both cards in a row at the same category_y/height even when only one
    # of them actually needs two lines, so paired cards stay level instead
    # of the short-titled one looking shorter/emptier than its neighbor.
    effective_title_lines = max(len(title_lines), row_title_lines)
    category_y = 54 if effective_title_lines == 1 else 31 + 16 + 23
    category_lines = item.get("category_lines") or wrap_words(item["category"], 38, 2)
    desc_y = category_y + 11 * len(category_lines) + 11
    desc_lines = _current_description_lines_desktop(item)
    desc_line_height = 15
    description_rows = max(len(desc_lines), row_description_lines)
    bottom_y = desc_y + desc_line_height * (description_rows - 1) + 13
    height = bottom_y + 9
    parts = svg_open(width, height, theme)
    add_image(parts, 10, 28, item["logo_width"], item["logo_height"], item["logo"], theme)
    text_x = 84
    add_multiline(parts, text_x, title_y, title_lines, "ui current-title", 16)
    add_multiline(parts, text_x, category_y, category_lines, "category", 11)
    add_multiline(parts, text_x, desc_y, desc_lines, "ui description", desc_line_height)
    if item.get("url"):
        add_arrow(parts, 371, 18)
    add_line(parts, 0, bottom_y, width, bottom_y)
    if index % 2 == 0 and index + 1 < total:
        add_line(parts, width - 1, 0, width - 1, bottom_y, True)
    return svg_close(parts)


def generate_cert_card(item: dict[str, Any], mobile: bool, theme: str) -> str:
    if mobile:
        width, height = MOBILE_WIDTH, 92
        parts = svg_open(width, height, theme)
        parts.append(f'<rect class="card-bg card-border" x=".5" y="4.5" width="{width - 1}" height="83" rx="10"/>')
        add_image(parts, 16, 31, item["logo_width"] + 8, item["logo_height"] + 3, item["logo"], theme)
        text_x = 137
        add_text(parts, text_x, 31, item["title"], "ui cert-title-mobile")
        add_text(parts, text_x, 55, item["subtitle"], "ui cert-subtitle-mobile")
        add_text(parts, text_x, 76, item["status"], "cert-status")
        return svg_close(parts)
    # Desktop is narrower than before (425 -> 390) so 2 cards reliably share a
    # row without an HTML width attribute (see responsive_picture). The
    # card-bg rect stops well short of the SVG's own width so the two cards
    # get a visible gap between them in the rendered README, since adjacent
    # <picture> tags are joined with no markup space between them.
    width, height = 390, 84
    card_width = 376
    parts = svg_open(width, height, theme)
    parts.append(f'<rect class="card-bg card-border" x="1" y="5" width="{card_width}" height="74" rx="9"/>')
    add_image(parts, 15, 28, item["logo_width"], item["logo_height"], item["logo"], theme)
    text_x = 130
    add_text(parts, text_x, 32, wrap_words(item["title"], 26, 1)[0], "ui cert-title")
    add_text(parts, text_x, 53, wrap_words(item["subtitle"], 38, 1)[0], "ui cert-subtitle")
    add_text(parts, text_x, 71, item["status"], "cert-status")
    return svg_close(parts)


def generate_header(title: str, mobile: bool, theme: str) -> str:
    width = MOBILE_WIDTH if mobile else 880
    height = 52 if mobile else 42
    parts = svg_open(width, height, theme)
    section_header(parts, title, width, mobile)
    return svg_close(parts)


def responsive_picture(name: str, alt: str, url: str | None = None) -> str:
    # GitHub web filters the links by fragment. The image URLs also carry the
    # marker for the mobile app, where <img> is the single-column fallback.
    base = "./assets/generated"
    pictures = []
    for theme in THEMES:
        marker = f"#gh-{theme}-mode-only"
        desktop = f"{base}/{name}-desktop-{theme}.svg"
        mobile = f"{base}/{name}-mobile-{theme}.svg"
        # For artwork without a destination, the fragment stays on the README.
        if url:
            anchor = f'<a href="{esc(urldefrag(url).url)}{marker}">'
        else:
            anchor = f'<a href="{marker}" tabindex="-1">'
        pictures.append(
            f'{anchor}<picture>'
            f'<source media="(min-width: {DESKTOP_BREAKPOINT}px)" srcset="{desktop}{marker}">'
            f'<img src="{mobile}{marker}" alt="{esc(alt)}">'
            '</picture></a>'
        )
    return "".join(pictures)


def generate_readme(profile: dict[str, Any]) -> str:
    status_alt = ". ".join(item["value"].replace(" @ ", " at ") for item in profile["status"])
    lines: list[str] = [
        '<div align="center">',
        responsive_picture("hero", "Iago Santana. Investigating threats. Solving real problems."),
        responsive_picture("status", status_alt),
        '</div>',
        '',
        '<br>',
        '',
        '<p align="center">',
    ]

    contact_pictures = [
        responsive_picture(f'contact-{item["label"].lower()}', item["label"].title(), item["url"])
        for item in profile["contacts"]
    ]
    lines.append("&#8195;&#8195;".join(contact_pictures))
    lines.extend(['</p>', '', '<div align="center">', responsive_picture("featured-header", "Featured work."), '<p align="center">'])
    featured_pictures = [
        responsive_picture(f"featured-card-{item_index}", item["title"], item.get("url"))
        for item_index, item in enumerate(profile["featured"])
    ]
    lines.append("".join(featured_pictures))
    lines.extend(['</p>', '</div>', ''])

    lines.extend(['<div align="center">', responsive_picture("current-header", "Other work.")])
    current_pictures = [
        responsive_picture(item.get("generated_name", f"current-{item_index}"), item["title"], item.get("url"))
        for item_index, item in enumerate(profile["current"])
    ]
    for row_start in range(0, len(current_pictures), 2):
        row = "".join(current_pictures[row_start:row_start + 2])
        lines.append(f'<div align="center">{row}</div>')
    lines.extend(['</div>', ''])
    if profile.get("certifications"):
        lines.extend([responsive_picture("certifications-header", "Certifications I'm pursuing."), '<p align="center">'])
        cert_pictures = [
            responsive_picture(f"cert-{i}", item["title"])
            for i, item in enumerate(profile["certifications"])
        ]
        lines.append("".join(cert_pictures))
        lines.extend(['</p>', ''])
    if profile.get("statistics"):
        lines.extend([
            responsive_picture("statistics-header", "GitHub profile statistics."),
            f'<img src="./{profile["statistics"]["path"]}" width="100%" alt="GitHub profile statistics">',
            '',
        ])
    lines.extend([
        '<details>',
        '<summary>Accessible text version</summary>',
        '',
        '## Featured work',
    ])
    for item in profile["featured"]:
        lines += [f'### {item["title"]}', f'*{item["category"]}*', '', item["description"], '']
    lines.append('## Other work')
    for item in profile["current"]:
        title = f'[{item["title"]}]({item["url"]})' if item.get("url") else item["title"]
        lines += [f'### {title}', f'*{item["category"]}*', '', item["description"], '']
    if profile.get("certifications"):
        lines.append("## Certifications I'm pursuing")
        for item in profile["certifications"]:
            lines.append(f'- [{item["title"]}]({item["url"]}) — {item["subtitle"]} — **{item["status"]}**')
    lines += ['', '</details>', '', '<!-- Generated from profile.yml. Edit profile.yml, then run python scripts/build_profile.py. -->', '']
    return "\n".join(lines)


def render_svg_string(svg_text: str, width: int, background: str) -> Image.Image:
    # cairosvg's text antialiasing produces color-fringed glyph edges (a subpixel/LCD
    # artifact) when rasterized directly at the target size. Supersampling and
    # downscaling with a quality filter blends those fringes back into neutral gray.
    supersample = 6
    raw_png = cairosvg.svg2png(bytestring=svg_text.encode("utf-8"), output_width=width * supersample)
    rendered = Image.open(io.BytesIO(raw_png)).convert("RGBA")
    rendered = rendered.resize((width, round(rendered.height / supersample)), Image.LANCZOS)
    bg = Image.new("RGBA", rendered.size, background)
    bg.alpha_composite(rendered)
    return bg.convert("RGB")


def render_svg_file(path: Path, width: int, background: str) -> Image.Image:
    return render_svg_string(path.read_text(encoding="utf-8"), width, background)


def stack_images(images: list[Image.Image], width: int, margin: int, gap: int, output: Path, background: str) -> None:
    height = margin * 2 + sum(i.height for i in images) + gap * (len(images) - 1)
    canvas = Image.new("RGB", (width + margin * 2, height), background)
    y = margin
    for image in images:
        canvas.paste(image, (margin, y))
        y += image.height + gap
    canvas.save(output, optimize=True)


def generate_previews(profile: dict[str, Any]) -> None:
    # Previews render each theme explicitly (cairosvg doesn't evaluate
    # prefers-color-scheme), by calling the generators directly with a fixed
    # theme rather than reading the theme-agnostic files written by
    # save_generated().
    DOCS.mkdir(parents=True, exist_ok=True)
    for theme in ("light", "dark"):
        bg = THEMES[theme]["preview_bg"]
        desktop: list[Image.Image] = [
            render_svg_string(generate_hero(profile, False, theme), 880, bg),
            render_svg_string(generate_status(profile, False, theme), 880, bg),
        ]
        contact_row = Image.new("RGB", (880, 76), bg)
        contact_gap = 20
        contact_width = 265
        contact_start = (880 - (len(profile["contacts"]) * contact_width + max(0, len(profile["contacts"]) - 1) * contact_gap)) // 2
        for index, item in enumerate(profile["contacts"]):
            x = contact_start + index * (contact_width + contact_gap)
            contact_row.paste(render_svg_string(generate_contact_card(item, False, theme), 265, bg), (x, 0))
        featured_row = Image.new("RGB", (880, 164), bg)
        featured_width = round((880 - 48) / 3)
        featured_x = (880 - featured_width * len(profile["featured"])) // 2
        for i, item in enumerate(profile["featured"]):
            card = render_svg_string(generate_featured_card(item, i, False, theme), featured_width, bg)
            featured_row.paste(card, (featured_x, 0))
            featured_x += card.width
        desktop += [
            contact_row,
            render_svg_string(generate_header("featured work", False, theme), 880, bg),
            featured_row,
            render_svg_string(generate_header("other work", False, theme), 880, bg),
        ]
        current_items = profile["current"]
        current_total = len(current_items)
        for i in range(0, current_total, 2):
            row_items = current_items[i:i + 2]
            row_title_lines = max(len(_current_title_lines_desktop(row_item)) for row_item in row_items)
            row_description_lines = max(len(_current_description_lines_desktop(row_item)) for row_item in row_items)
            row_cards = [
                render_svg_string(
                    generate_current_card(
                        item, False, theme, i + offset, current_total, row_title_lines, row_description_lines
                    ),
                    390, bg,
                )
                for offset, item in enumerate(row_items)
            ]
            row_height = max(card.height for card in row_cards)
            row = Image.new("RGB", (880, row_height), bg)
            card_x = (row.width - sum(card.width for card in row_cards)) // 2
            for card in row_cards:
                row.paste(card, (card_x, 0))
                card_x += card.width
            desktop.append(row)
        if profile.get("certifications"):
            desktop.append(render_svg_string(generate_header("certifications i'm pursuing", False, theme), 880, bg))
            cert_row = Image.new("RGB", (880, 84), bg)
            for index, item in enumerate(profile["certifications"][:2]):
                cert_row.paste(render_svg_string(generate_cert_card(item, False, theme), 390, bg), (index * 410, 0))
            desktop.append(cert_row)
        if profile.get("statistics"):
            desktop.append(render_svg_string(generate_header("github profile statistics", False, theme), 880, bg))
            desktop.append(render_svg_file(ROOT/profile["statistics"]["path"], 880, bg))
        stack_images(desktop, 880, 24, 12, DOCS/f"preview-desktop-{theme}.png", bg)

        mobile: list[Image.Image] = [
            render_svg_string(generate_hero(profile, True, theme), MOBILE_WIDTH, bg),
            render_svg_string(generate_status(profile, True, theme), MOBILE_WIDTH, bg),
        ]
        for item in profile["contacts"]:
            mobile.append(render_svg_string(generate_contact_card(item, True, theme), MOBILE_WIDTH, bg))
        mobile.append(render_svg_string(generate_header("featured work", True, theme), MOBILE_WIDTH, bg))
        for i, item in enumerate(profile["featured"]):
            mobile.append(render_svg_string(generate_featured_card(item, i, True, theme), MOBILE_WIDTH, bg))
        mobile.append(render_svg_string(generate_header("other work", True, theme), MOBILE_WIDTH, bg))
        for item in profile["current"]:
            mobile.append(render_svg_string(generate_current_card(item, True, theme), MOBILE_WIDTH, bg))
        if profile.get("certifications"):
            mobile.append(render_svg_string(generate_header("certifications i'm pursuing", True, theme), MOBILE_WIDTH, bg))
            for item in profile["certifications"]:
                mobile.append(render_svg_string(generate_cert_card(item, True, theme), MOBILE_WIDTH, bg))
        if profile.get("statistics"):
            mobile.append(render_svg_string(generate_header("github profile statistics", True, theme), MOBILE_WIDTH, bg))
            mobile.append(render_svg_file(ROOT/profile["statistics"]["path"], MOBILE_WIDTH, bg))
        stack_images(mobile, MOBILE_WIDTH, 15, 10, DOCS/f"preview-mobile-{theme}.png", bg)


def update_contents() -> None:
    paths = (path.relative_to(ROOT) for path in ROOT.rglob("*") if path.is_file())
    files = sorted(
        path.as_posix() for path in paths
        if path.parts[0] != ".git" and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )
    (ROOT / "REPOSITORY-CONTENTS.txt").write_text("\n".join(files) + "\n", encoding="utf-8", newline="\n")


def save_generated(profile: dict[str, Any]) -> None:
    if GENERATED.exists():
        shutil.rmtree(GENERATED)
    GENERATED.mkdir(parents=True, exist_ok=True)
    for (mobile, layout), theme in product(((False, "desktop"), (True, "mobile")), THEMES):
        suffix = f"-{layout}-{theme}.svg"
        outputs = {
            "hero": generate_hero(profile, mobile, theme),
            "status": generate_status(profile, mobile, theme),
            "featured": generate_featured(profile, mobile, theme),
            "featured-header": generate_header("featured work", mobile, theme),
            "current-header": generate_header("other work", mobile, theme),
        }
        if profile.get("certifications"):
            outputs["certifications-header"] = generate_header("certifications i'm pursuing", mobile, theme)
        if profile.get("statistics"):
            outputs["statistics-header"] = generate_header("github profile statistics", mobile, theme)
        for i, item in enumerate(profile["featured"]):
            outputs[f"featured-card-{i}"] = generate_featured_card(item, i, mobile, theme)
        for item in profile["contacts"]:
            outputs[f'contact-{item["label"].lower()}'] = generate_contact_card(item, mobile, theme)
        current_total = len(profile["current"])
        current_items = profile["current"]
        for i, item in enumerate(current_items):
            current_name = item.get("generated_name", f"current-{i}")
            row_title_lines = 1
            row_description_lines = 1
            if not mobile:
                row_start = i - (i % 2)
                row_items = current_items[row_start:row_start + 2]
                row_title_lines = max(len(_current_title_lines_desktop(row_item)) for row_item in row_items)
                row_description_lines = max(len(_current_description_lines_desktop(row_item)) for row_item in row_items)
            outputs[current_name] = generate_current_card(
                item, mobile, theme, i, current_total, row_title_lines, row_description_lines
            )
        for i, item in enumerate(profile.get("certifications", [])):
            outputs[f"cert-{i}"] = generate_cert_card(item, mobile, theme)
        for name, content in outputs.items():
            (GENERATED / f"{name}{suffix}").write_text(content, encoding="utf-8", newline="\n")

    (ROOT / "README.md").write_text(generate_readme(profile), encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-preview", action="store_true")
    args = parser.parse_args()
    profile = load_profile()
    save_generated(profile)
    if not args.no_preview:
        generate_previews(profile)
    update_contents()
    print("Profile generated successfully.")


if __name__ == "__main__":
    main()
