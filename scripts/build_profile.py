#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import html
import io
import shutil
from pathlib import Path
from typing import Any

import cairosvg
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "assets" / "generated"
# Below this viewport width, the mobile SVG variant is served. Kept well under
# typical desktop widths (even scaled down by OS display scaling) so a real
# computer window never accidentally matches it — only phones should.
MOBILE_BREAKPOINT = 480
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
.card-bg{{fill:{c['card']}}}
.card-border{{stroke:{c['card_border']}}}
.line{{stroke:{c['line']}}}
.soft-line{{stroke:{c['soft_line']}}}
.icon-disc{{fill:{c['icon_disc']};stroke:{c['card_border']}}}
.arrow{{stroke:{c['arrow']};fill:{c['arrow']}}}
.hero-headline{{font:italic 600 34px Georgia,'Times New Roman',serif;fill:{c['text']}}}
.hero-headline-mobile{{font:italic 600 12px Georgia,'Times New Roman',serif;letter-spacing:-.1px;fill:{c['text']}}}
.hero-copy{{font:400 11px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;fill:{c['muted']}}}
.hero-copy-mobile{{font:400 9.5px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;letter-spacing:-.08px;fill:{c['muted']}}}
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
.title-mobile{{font-size:16px;font-weight:700;letter-spacing:-.12px}}
.current-title{{font-size:14px;font-weight:700;letter-spacing:-.1px}}
.current-title-mobile{{font-size:15.5px;font-weight:700;letter-spacing:-.1px}}
.category{{font:700 10px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;letter-spacing:1.2px;fill:{c['label']}}}
.category-mobile{{font:700 7.8px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;letter-spacing:1.15px;fill:{c['label']}}}
.description{{font-size:11.3px;font-weight:400;fill:{c['muted']}}}
.description-mobile{{font-size:12.6px;font-weight:400;fill:{c['muted']}}}
.cert-title{{font-size:15px;font-weight:700;letter-spacing:-.12px}}
.cert-title-mobile{{font-size:15.5px;font-weight:700;letter-spacing:-.12px}}
.cert-subtitle{{font-size:10.5px;font-weight:400;fill:{c['muted']}}}
.cert-subtitle-mobile{{font-size:11px;font-weight:400;fill:{c['muted']}}}
.cert-status{{font:700 7.4px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;letter-spacing:1.4px;fill:{c['label']}}}
"""


def style(theme: str | None) -> str:
    # theme="light"/"dark" renders a single fixed palette, unconditionally — used
    # only to rasterize the local preview PNGs (docs/), where nothing evaluates
    # `prefers-color-scheme` for us.
    #
    # theme=None (the real, shipped files) embeds BOTH palettes in one file: light
    # values are the default rules, dark values live inside a native
    # `@media (prefers-color-scheme: dark)` block. This is evaluated by the
    # browser while it rasterizes the SVG image itself, so it works regardless of
    # how GitHub's own theme-switching machinery treats the <picture>/<source>
    # elements around it — that machinery is only ever given a single, theme-
    # agnostic image URL per breakpoint (see responsive_picture()).
    if theme in ("light", "dark"):
        return _theme_rules(THEMES[theme])
    dark_block = _theme_rules(THEMES["dark"]) + ".theme-light-only{display:none}.theme-dark-only{display:block}"
    return _theme_rules(THEMES["light"]) + ".theme-dark-only{display:none}" + f"@media (prefers-color-scheme: dark){{{dark_block}}}"


def svg_open(width: int, height: int, theme: str | None) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<style>{style(theme)}</style>',
    ]


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


def add_image(parts: list[str], x: float, y: float, width: float, height: float, relative: str, theme: str | None) -> None:
    path = ROOT / relative
    has_dark = path.with_name(f"{path.stem}-dark{path.suffix}").exists()
    attrs = f'x="{x}" y="{y}" width="{width}" height="{height}" preserveAspectRatio="xMidYMid meet"'
    if theme in ("light", "dark") or not has_dark:
        pick = "dark" if (theme == "dark" and has_dark) else "light"
        parts.append(f'<image href="{data_uri(relative, pick)}" {attrs}/>')
        return
    # Theme-agnostic file: embed both, toggled by the same native media query
    # used for the rest of the palette (see style()).
    parts.append(f'<g class="theme-light-only"><image href="{data_uri(relative, "light")}" {attrs}/></g>')
    parts.append(f'<g class="theme-dark-only"><image href="{data_uri(relative, "dark")}" {attrs}/></g>')


def add_line(parts: list[str], x1: float, y1: float, x2: float, y2: float, soft: bool = False) -> None:
    parts.append(f'<line class="{"soft-line" if soft else "line"}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>')


def add_arrow(parts: list[str], x: float, y: float) -> None:
    parts.append(
        f'<path d="M{x-4} {y+4} L{x+4} {y-4} M{x-1} {y-4} H{x+4} V{y+1}" '
        'fill="none" class="arrow" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def wrap_words(value: str, max_chars: int, max_lines: int) -> list[str]:
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
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .") + "…"
    return lines or [""]


def section_header(parts: list[str], title: str, width: int, mobile: bool) -> None:
    left = 16 if mobile else 2
    right = width - (16 if mobile else 2)
    add_text(parts, left, 27 if mobile else 22, title, "ui section-mobile" if mobile else "ui section")
    add_line(parts, left, 43 if mobile else 35, right, 43 if mobile else 35)


def generate_hero(profile: dict[str, Any], mobile: bool, theme: str | None) -> str:
    # Both lines are rendered in fonts that GitHub's real renderer substitutes per-OS
    # (e.g. Consolas/Courier New on Windows for the monospace stack, or a wider
    # Georgia fallback for the headline) — measurably wider than what the font used
    # to preview this locally. Font sizes carry a real safety margin (calibrated
    # from an actual overflow seen in a browser, not a local render), and both
    # lines wrap defensively instead of relying on an exact single-line fit.
    meta = profile["meta"]
    if mobile:
        width = 360
        headline_line_height, copy_line_height = 15, 12
        headline_lines = wrap_words(meta["headline"], max_chars=46, max_lines=2)
        copy_lines = wrap_words(meta["introduction"], max_chars=24, max_lines=4)
        headline_y = 30
        copy_y = headline_y + headline_line_height * (len(headline_lines) - 1) + 20
        bottom_y = copy_y + copy_line_height * (len(copy_lines) - 1) + 16
        height = bottom_y + 5
        parts = svg_open(width, height, theme)
        add_line(parts, 16, 4, 344, 4)
        add_multiline(parts, 16, headline_y, headline_lines, "hero-headline-mobile", headline_line_height)
        add_multiline(parts, 16, copy_y, copy_lines, "hero-copy-mobile", copy_line_height)
        add_line(parts, 16, bottom_y, 344, bottom_y)
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


def generate_status(profile: dict[str, Any], mobile: bool, theme: str | None) -> str:
    items = profile["status"]
    if mobile:
        width, height = 360, 188
        parts = svg_open(width, height, theme)
        add_line(parts, 16, 2, 344, 2)
        for i, item in enumerate(items):
            y = 13 + i * 60
            add_text(parts, 16, y + 13, item["label"], "status-label")
            add_text(parts, 16, y + 39, item["value"], "status-value-mobile")
            add_line(parts, 16, y + 51, 344, y + 51)
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


def generate_contact_card(item: dict[str, Any], mobile: bool, theme: str | None) -> str:
    # Desktop is narrower than before (280 -> 265) so 3 cards reliably share one
    # row without an HTML width attribute (see responsive_linked_picture). The
    # value wraps defensively instead of assuming it always fits one line.
    width, height = (360, 78) if mobile else (265, 76)
    parts = svg_open(width, height, theme)
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


def generate_featured(profile: dict[str, Any], mobile: bool, theme: str | None) -> str:
    items = profile["featured"]
    if mobile:
        width = 360
        start = 57
        row_heights = [int(item.get("row_height", 146)) for item in items]
        height = start + sum(row_heights) + 5
        parts = svg_open(width, height, theme)
        section_header(parts, "featured work", width, True)
        y = start
        for i, item in enumerate(items):
            row_h = row_heights[i]
            add_image(parts, 18, y + 19, item["logo_width"] + 6, item["logo_height"] + 6, item["logo"], theme)
            add_multiline(parts, 92, y + 29, item["title_lines"], "ui title-mobile", 20)
            category_lines = item.get("category_lines", [item["category"]])
            add_multiline(parts, 92, y + 73, category_lines, "category-mobile", 11)
            description_lines = wrap_words(item["description"], 35, int(item.get("description_max_lines", 3)))
            add_multiline(parts, 92, y + 98 + 11 * (len(category_lines) - 1), description_lines, "ui description-mobile", 17)
            if item.get("url"):
                add_arrow(parts, 337, y + 18)
            add_line(parts, 16, y + row_h - 4, 344, y + row_h - 4)
            y += row_h
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


def generate_featured_card(item: dict[str, Any], index: int, mobile: bool, theme: str | None) -> str:
    """Render one featured-work card so it can be wrapped in its own link."""
    if mobile:
        width = 360
        row_h = int(item.get("row_height", 146))
        parts = svg_open(width, row_h, theme)
        add_image(parts, 18, 19, item["logo_width"] + 6, item["logo_height"] + 6, item["logo"], theme)
        add_multiline(parts, 92, 29, item["title_lines"], "ui title-mobile", 20)
        category_lines = item.get("category_lines", [item["category"]])
        add_multiline(parts, 92, 73, category_lines, "category-mobile", 11)
        description_lines = wrap_words(item["description"], 35, int(item.get("description_max_lines", 3)))
        add_multiline(parts, 92, 98 + 11 * (len(category_lines) - 1), description_lines, "ui description-mobile", 17)
        if item.get("url"):
            add_arrow(parts, 337, 18)
        add_line(parts, 16, row_h - 4, 344, row_h - 4)
        return svg_close(parts)

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


def generate_current_card(item: dict[str, Any], mobile: bool, theme: str | None) -> str:
    if mobile:
        width = 360
        title_lines = wrap_words(item["title"], 34, 2)
        category_y = 68 if len(title_lines) == 2 else 53
        category_lines = wrap_words(item["category"], 34, 2)
        desc_y = category_y + 11 * (len(category_lines) - 1) + 25
        desc_lines = wrap_words(item["description"], 38, 3)
        bottom_y = desc_y + 17 * (len(desc_lines) - 1) + 22
        height = bottom_y + 5
        parts = svg_open(width, height, theme)
        add_image(parts, 16, 29, item["logo_width"] + 4, item["logo_height"] + 4, item["logo"], theme)
        text_x = 92
        add_multiline(parts, text_x, 28, title_lines, "ui current-title-mobile", 18)
        add_multiline(parts, text_x, category_y, category_lines, "category-mobile", 11)
        add_multiline(parts, text_x, desc_y, desc_lines, "ui description-mobile", 17)
        if item.get("url"):
            add_arrow(parts, 337, 18)
        add_line(parts, 16, bottom_y, 344, bottom_y)
        return svg_close(parts)
    # Desktop is narrower than before (425 -> 390) so 2 cards reliably share a
    # row without an HTML width attribute (see responsive_linked_picture). The
    # description now wraps across up to 3 (tighter) lines instead of 2 wider
    # ones, so per-line width doesn't have to shrink as much. Category and
    # description position/height are both computed from actual line counts
    # rather than assumed to always be 1 and 3 lines respectively.
    width = 390
    category_lines = wrap_words(item["category"], 32, 2)
    desc_y = 54 + 11 * len(category_lines) + 11
    desc_lines = wrap_words(item["description"], 38, 3)
    desc_line_height = 15
    bottom_y = desc_y + desc_line_height * (len(desc_lines) - 1) + 13
    height = bottom_y + 9
    parts = svg_open(width, height, theme)
    add_image(parts, 10, 28, item["logo_width"], item["logo_height"], item["logo"], theme)
    text_x = 84
    title_lines = item.get("title_lines_desktop") or wrap_words(item["title"], 39, 2)
    title_y = 31 if len(title_lines) == 1 else 23
    add_multiline(parts, text_x, title_y, title_lines, "ui current-title", 16)
    add_multiline(parts, text_x, 54, category_lines, "category", 11)
    add_multiline(parts, text_x, desc_y, desc_lines, "ui description", desc_line_height)
    if item.get("url"):
        add_arrow(parts, 371, 18)
    add_line(parts, 0, bottom_y, width, bottom_y)
    return svg_close(parts)


def generate_cert_card(item: dict[str, Any], mobile: bool, theme: str | None) -> str:
    if mobile:
        width, height = 360, 92
        parts = svg_open(width, height, theme)
        parts.append('<rect class="card-bg card-border" x=".5" y="4.5" width="359" height="83" rx="10"/>')
        add_image(parts, 16, 31, item["logo_width"] + 8, item["logo_height"] + 3, item["logo"], theme)
        text_x = 137
        add_text(parts, text_x, 31, item["title"], "ui cert-title-mobile")
        add_text(parts, text_x, 55, item["subtitle"], "ui cert-subtitle-mobile")
        add_text(parts, text_x, 76, item["status"], "cert-status")
        add_arrow(parts, 337, 20)
        return svg_close(parts)
    # Desktop is narrower than before (425 -> 390) so 2 cards reliably share a
    # row without an HTML width attribute (see responsive_linked_picture).
    width, height = 390, 84
    parts = svg_open(width, height, theme)
    parts.append(f'<rect class="card-bg card-border" x="1" y="5" width="{width-2}" height="74" rx="9"/>')
    add_image(parts, 15, 28, item["logo_width"], item["logo_height"], item["logo"], theme)
    text_x = 130
    add_text(parts, text_x, 32, wrap_words(item["title"], 26, 1)[0], "ui cert-title")
    add_text(parts, text_x, 53, wrap_words(item["subtitle"], 38, 1)[0], "ui cert-subtitle")
    add_text(parts, text_x, 71, item["status"], "cert-status")
    add_arrow(parts, width - 20, 21)
    return svg_close(parts)


def generate_header(title: str, mobile: bool, theme: str | None) -> str:
    width = 360 if mobile else 880
    height = 52 if mobile else 42
    parts = svg_open(width, height, theme)
    section_header(parts, title, width, mobile)
    return svg_close(parts)


def responsive_picture(name: str, alt: str) -> str:
    # Only ever gated on width. Theme is handled *inside* each SVG via a native
    # prefers-color-scheme media query (see style()) — not here. GitHub wraps
    # README <picture> elements in its own <themed-picture> custom element to
    # drive dark/light from the site's theme setting; empirically (checked via
    # a live browser: window.innerWidth confirmed at 1920px, yet it still served
    # the mobile-breakpoint source) it does not reliably honour a width bound
    # combined with a color-scheme condition on the same <source>, regardless of
    # how explicitly both are qualified. Giving it nothing color-scheme-related
    # to look at sidesteps that entirely.
    base = "./assets/generated"
    return (
        '<picture>\n'
        f'  <source media="(max-width: {MOBILE_BREAKPOINT}px)" srcset="{base}/{name}-mobile.svg">\n'
        f'  <img src="{base}/{name}-desktop.svg" width="100%" alt="{esc(alt)}">\n'
        '</picture>'
    )


def responsive_linked_picture(path_base: str, alt: str, url: str | None) -> str:
    # Deliberately no width attribute on the desktop <img> — setting one
    # (tried as a percentage, to get 3 contact cards / 2 current-cert cards
    # sharing a row regardless of GitHub's exact content-column width) broke
    # mobile source selection: confirmed live, in both the GitHub app and
    # mobile Safari, the mobile <source> stopped being picked and the desktop
    # image rendered instead, scaled down. Row-fit on desktop is handled by
    # sizing each card's own SVG small enough to fit, not by an HTML width
    # attribute on the <picture>.
    base = "./assets/generated"
    picture = (
        '<picture>'
        f'<source media="(max-width: {MOBILE_BREAKPOINT}px)" srcset="{base}/{path_base}-mobile.svg">'
        f'<img src="{base}/{path_base}-desktop.svg" alt="{esc(alt)}">'
        '</picture>'
    )
    return f'<a href="{esc(url)}">{picture}</a>' if url else picture


def generate_readme(profile: dict[str, Any]) -> str:
    lines: list[str] = [
        '<div align="center">',
        responsive_picture("hero", "Iago Santana. Investigating threats. Solving real problems."),
        responsive_picture("status", "Working in SOC and CTI at iT.EAM, researching LLM Security and studying Computer Engineering at CEFET-MG."),
        '</div>',
        '',
        '<br>',
        '',
        '<p align="center">',
    ]

    contact_pictures = [
        responsive_linked_picture(f'contact-{item["label"].lower()}', item["label"].title(), item["url"])
        for item in profile["contacts"]
    ]
    lines.append("&#8195;&#8195;".join(contact_pictures))
    lines.extend(['</p>', '', '<div align="center">', responsive_picture("featured-header", "Featured work in SOC and CTI, LLM Security and post-quantum cryptography research."), '<p align="center">'])
    featured_pictures = [
        responsive_linked_picture(f"featured-card-{item_index}", item["title"], item.get("url"))
        for item_index, item in enumerate(profile["featured"])
    ]
    lines.append("".join(featured_pictures))
    lines.extend(['</p>', '</div>', ''])

    lines.append(responsive_picture("current-header", "Other work."))
    lines.append('<p align="center">')
    current_pictures = [
        responsive_linked_picture(item.get("generated_name", f"current-{item_index}"), item["title"], item.get("url"))
        for item_index, item in enumerate(profile["current"])
    ]
    lines.append("".join(current_pictures))
    lines.extend(['</p>', '', responsive_picture("certifications-header", "Certifications."), '<p align="center">'])

    cert_pictures = [
        responsive_linked_picture(f"cert-{i}", item["title"], item["url"])
        for i, item in enumerate(profile["certifications"])
    ]
    lines.append("".join(cert_pictures))
    lines.extend([
        '</p>',
        '',
        responsive_picture("statistics-header", "GitHub profile statistics."),
        f'<img src="./{profile["statistics"]["path"]}" width="100%" alt="GitHub profile statistics">',
        '',
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
    lines.append('## Certifications')
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
        current_cards = [render_svg_string(generate_current_card(item, False, theme), 390, bg) for item in profile["current"]]
        for i in range(0, len(current_cards), 2):
            row = Image.new("RGB", (880, 139), bg)
            row.paste(current_cards[i], (0, 0))
            if i + 1 < len(current_cards):
                row.paste(current_cards[i + 1], (410, 0))
            desktop.append(row)
        desktop.append(render_svg_string(generate_header("certifications", False, theme), 880, bg))
        cert_row = Image.new("RGB", (880, 84), bg)
        cert_row.paste(render_svg_string(generate_cert_card(profile["certifications"][0], False, theme), 390, bg), (0, 0))
        cert_row.paste(render_svg_string(generate_cert_card(profile["certifications"][1], False, theme), 390, bg), (410, 0))
        desktop.append(cert_row)
        desktop.append(render_svg_string(generate_header("github profile statistics", False, theme), 880, bg))
        desktop.append(render_svg_file(ROOT/profile["statistics"]["path"], 880, bg))
        stack_images(desktop, 880, 24, 12, DOCS/f"preview-desktop-{theme}.png", bg)

        mobile: list[Image.Image] = [
            render_svg_string(generate_hero(profile, True, theme), 360, bg),
            render_svg_string(generate_status(profile, True, theme), 360, bg),
        ]
        for item in profile["contacts"]:
            mobile.append(render_svg_string(generate_contact_card(item, True, theme), 360, bg))
        mobile.append(render_svg_string(generate_header("featured work", True, theme), 360, bg))
        for i, item in enumerate(profile["featured"]):
            mobile.append(render_svg_string(generate_featured_card(item, i, True, theme), 360, bg))
        mobile.append(render_svg_string(generate_header("other work", True, theme), 360, bg))
        for item in profile["current"]:
            mobile.append(render_svg_string(generate_current_card(item, True, theme), 360, bg))
        mobile.append(render_svg_string(generate_header("certifications", True, theme), 360, bg))
        for item in profile["certifications"]:
            mobile.append(render_svg_string(generate_cert_card(item, True, theme), 360, bg))
        mobile.append(render_svg_string(generate_header("github profile statistics", True, theme), 360, bg))
        mobile.append(render_svg_file(ROOT/profile["statistics"]["path"], 360, bg))
        stack_images(mobile, 360, 15, 10, DOCS/f"preview-mobile-{theme}.png", bg)


def update_contents() -> None:
    files = sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    (ROOT / "REPOSITORY-CONTENTS.txt").write_text("\n".join(files) + "\n", encoding="utf-8")


def save_generated(profile: dict[str, Any]) -> None:
    if GENERATED.exists():
        shutil.rmtree(GENERATED)
    GENERATED.mkdir(parents=True, exist_ok=True)
    for mobile, layout in ((False, "desktop"), (True, "mobile")):
        outputs = {
            f"hero-{layout}.svg": generate_hero(profile, mobile, None),
            f"status-{layout}.svg": generate_status(profile, mobile, None),
            f"featured-{layout}.svg": generate_featured(profile, mobile, None),
            f"featured-header-{layout}.svg": generate_header("featured work", mobile, None),
            f"current-header-{layout}.svg": generate_header("other work", mobile, None),
            f"certifications-header-{layout}.svg": generate_header("certifications", mobile, None),
            f"statistics-header-{layout}.svg": generate_header("github profile statistics", mobile, None),
        }
        for i, item in enumerate(profile["featured"]):
            outputs[f"featured-card-{i}-{layout}.svg"] = generate_featured_card(item, i, mobile, None)
        for item in profile["contacts"]:
            outputs[f'contact-{item["label"].lower()}-{layout}.svg'] = generate_contact_card(item, mobile, None)
        for i, item in enumerate(profile["current"]):
            current_name = item.get("generated_name", f"current-{i}")
            outputs[f"{current_name}-{layout}.svg"] = generate_current_card(item, mobile, None)
        for i, item in enumerate(profile["certifications"]):
            outputs[f"cert-{i}-{layout}.svg"] = generate_cert_card(item, mobile, None)
        for name, content in outputs.items():
            (GENERATED / name).write_text(content, encoding="utf-8")

    (ROOT / "README.md").write_text(generate_readme(profile), encoding="utf-8")


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
