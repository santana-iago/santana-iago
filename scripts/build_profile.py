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


def style(theme: str) -> str:
    c = THEMES[theme]
    return f"""
.card-bg{{fill:{c['card']}}}
.card-border{{stroke:{c['card_border']}}}
.line{{stroke:{c['line']}}}
.soft-line{{stroke:{c['soft_line']}}}
.icon-disc{{fill:{c['icon_disc']};stroke:{c['card_border']}}}
.arrow{{stroke:{c['arrow']};fill:{c['arrow']}}}
.hero-headline{{font:italic 600 38px Georgia,'Times New Roman',serif;fill:{c['text']}}}
.hero-headline-mobile{{font:italic 600 15px Georgia,'Times New Roman',serif;letter-spacing:-.16px;fill:{c['text']}}}
.hero-copy{{font:400 16px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;fill:{c['muted']}}}
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
.category{{font:700 7.3px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;letter-spacing:1.2px;fill:{c['label']}}}
.category-mobile{{font:700 7.8px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;letter-spacing:1.15px;fill:{c['label']}}}
.description{{font-size:11.3px;font-weight:400;fill:{c['muted']}}}
.description-mobile{{font-size:12.6px;font-weight:400;fill:{c['muted']}}}
.cert-title{{font-size:15px;font-weight:700;letter-spacing:-.12px}}
.cert-title-mobile{{font-size:15.5px;font-weight:700;letter-spacing:-.12px}}
.cert-subtitle{{font-size:10.5px;font-weight:400;fill:{c['muted']}}}
.cert-subtitle-mobile{{font-size:11px;font-weight:400;fill:{c['muted']}}}
.cert-status{{font:700 7.4px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;letter-spacing:1.4px;fill:{c['label']}}}
"""


def svg_open(width: int, height: int, theme: str) -> list[str]:
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


def add_image(parts: list[str], x: float, y: float, width: float, height: float, relative: str, theme: str) -> None:
    parts.append(
        f'<image href="{data_uri(relative, theme)}" x="{x}" y="{y}" width="{width}" height="{height}" '
        'preserveAspectRatio="xMidYMid meet"/>'
    )


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


def generate_hero(profile: dict[str, Any], mobile: bool, theme: str) -> str:
    meta = profile["meta"]
    if mobile:
        width, height = 360, 110
        parts = svg_open(width, height, theme)
        add_line(parts, 16, 4, 344, 4)
        add_text(parts, 16, 46, meta["headline"], "hero-headline-mobile")
        add_text(parts, 16, 76, meta["introduction"], "hero-copy-mobile")
        add_line(parts, 16, 105, 344, 105)
        return svg_close(parts)
    width, height = 880, 154
    parts = svg_open(width, height, theme)
    add_line(parts, 2, 8, 878, 8)
    add_text(parts, 2, 72, meta["headline"], "hero-headline")
    add_text(parts, 4, 114, meta["introduction"], "hero-copy")
    add_line(parts, 2, 145, 878, 145)
    return svg_close(parts)


def generate_status(profile: dict[str, Any], mobile: bool, theme: str) -> str:
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


def generate_contact_card(item: dict[str, Any], mobile: bool, theme: str) -> str:
    width, height = (360, 78) if mobile else (280, 76)
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
    add_text(parts, 60, cy+14, item["value"], "contact-value-mobile" if mobile else "contact-value")
    add_arrow(parts, width-20, cy)
    return svg_close(parts)


def generate_featured(profile: dict[str, Any], mobile: bool, theme: str) -> str:
    items = profile["featured"]
    if mobile:
        width, height = 360, 500
        parts = svg_open(width, height, theme)
        section_header(parts, "featured work", width, True)
        start, row_h = 57, 146
        for i, item in enumerate(items):
            y = start + i * row_h
            add_image(parts, 18, y + 19, item["logo_width"] + 6, item["logo_height"] + 6, item["logo"], theme)
            add_multiline(parts, 92, y + 29, item["title_lines"], "ui title-mobile", 20)
            add_text(parts, 92, y + 73, item["category"], "category-mobile")
            add_multiline(parts, 92, y + 98, wrap_words(item["description"], 35, 3), "ui description-mobile", 17)
            add_line(parts, 16, y + row_h - 4, 344, y + row_h - 4)
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
        add_text(parts, x + 72, top + 62, item["category"], "category")
        add_multiline(parts, x + 8, top + 91, wrap_words(item["description"], 38, 3), "ui description", 17)
        add_line(parts, x, 218, x + col_w, 218)
    return svg_close(parts)


def generate_current_card(item: dict[str, Any], mobile: bool, theme: str) -> str:
    if mobile:
        width, height = 360, 142
        parts = svg_open(width, height, theme)
        add_image(parts, 16, 29, item["logo_width"] + 4, item["logo_height"] + 4, item["logo"], theme)
        text_x = 92
        title_lines = wrap_words(item["title"], 34, 2)
        add_multiline(parts, text_x, 28, title_lines, "ui current-title-mobile", 18)
        category_y = 68 if len(title_lines) == 2 else 53
        add_text(parts, text_x, category_y, item["category"], "category-mobile")
        add_multiline(parts, text_x, category_y + 25, wrap_words(item["description"], 38, 3), "ui description-mobile", 17)
        if item.get("url"):
            add_arrow(parts, 337, 18)
        add_line(parts, 16, 139, 344, 139)
        return svg_close(parts)
    width, height = 425, 108
    parts = svg_open(width, height, theme)
    add_image(parts, 10, 28, item["logo_width"], item["logo_height"], item["logo"], theme)
    text_x = 84
    title_lines = wrap_words(item["title"], 44, 2)
    title_y = 31 if len(title_lines) == 1 else 23
    add_multiline(parts, text_x, title_y, title_lines, "ui current-title", 16)
    add_text(parts, text_x, 54, item["category"], "category")
    add_multiline(parts, text_x, 76, wrap_words(item["description"], 51, 2), "ui description", 16)
    if item.get("url"):
        add_arrow(parts, 406, 18)
    add_line(parts, 0, 105, 425, 105)
    return svg_close(parts)


def generate_cert_card(item: dict[str, Any], mobile: bool, theme: str) -> str:
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
    width, height = 425, 84
    parts = svg_open(width, height, theme)
    parts.append('<rect class="card-bg card-border" x="1" y="5" width="423" height="74" rx="9"/>')
    add_image(parts, 15, 28, item["logo_width"], item["logo_height"], item["logo"], theme)
    text_x = 130
    add_text(parts, text_x, 32, item["title"], "ui cert-title")
    add_text(parts, text_x, 53, item["subtitle"], "ui cert-subtitle")
    add_text(parts, text_x, 71, item["status"], "cert-status")
    add_arrow(parts, 405, 21)
    return svg_close(parts)


def generate_header(title: str, mobile: bool, theme: str) -> str:
    width = 360 if mobile else 880
    height = 52 if mobile else 42
    parts = svg_open(width, height, theme)
    section_header(parts, title, width, mobile)
    return svg_close(parts)


def responsive_picture(name: str, alt: str) -> str:
    base = "./assets/generated"
    return (
        '<picture>\n'
        f'  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="{base}/{name}-mobile-dark.svg">\n'
        f'  <source media="(max-width: 640px)" srcset="{base}/{name}-mobile-light.svg">\n'
        f'  <source media="(prefers-color-scheme: dark)" srcset="{base}/{name}-desktop-dark.svg">\n'
        f'  <img src="{base}/{name}-desktop-light.svg" width="100%" alt="{esc(alt)}">\n'
        '</picture>'
    )


def responsive_linked_picture(path_base: str, alt: str, url: str | None) -> str:
    base = "./assets/generated"
    picture = (
        '<picture>'
        f'<source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="{base}/{path_base}-mobile-dark.svg">'
        f'<source media="(max-width: 640px)" srcset="{base}/{path_base}-mobile-light.svg">'
        f'<source media="(prefers-color-scheme: dark)" srcset="{base}/{path_base}-desktop-dark.svg">'
        f'<img src="{base}/{path_base}-desktop-light.svg" alt="{esc(alt)}">'
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

    for item in profile["contacts"]:
        lines.append(responsive_linked_picture(f'contact-{item["label"].lower()}', item["label"].title(), item["url"]))
    lines.extend(['</p>', '', '<div align="center">', responsive_picture("featured", "Featured work in SOC and CTI, LLM Security and post-quantum cryptography research."), '</div>', ''])

    lines.append(responsive_picture("current-header", "Currently working on."))
    lines.append('<p align="center">')
    for item_index, item in enumerate(profile["current"]):
        lines.append(responsive_linked_picture(f"current-{item_index}", item["title"], item.get("url")))
    lines.extend(['</p>', '', responsive_picture("certifications-header", "Certifications."), '<p align="center">'])

    for i, item in enumerate(profile["certifications"]):
        lines.append(responsive_linked_picture(f"cert-{i}", item["title"], item["url"]))
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
    lines.append('## Currently working on')
    for item in profile["current"]:
        title = f'[{item["title"]}]({item["url"]})' if item.get("url") else item["title"]
        lines += [f'### {title}', f'*{item["category"]}*', '', item["description"], '']
    lines.append('## Certifications')
    for item in profile["certifications"]:
        lines.append(f'- [{item["title"]}]({item["url"]}) — {item["subtitle"]} — **{item["status"]}**')
    lines += ['', '</details>', '', '<!-- Generated from profile.yml. Edit profile.yml, then run python scripts/build_profile.py. -->', '']
    return "\n".join(lines)


def render_svg(path: Path, width: int, background: str) -> Image.Image:
    # cairosvg's text antialiasing produces color-fringed glyph edges (a subpixel/LCD
    # artifact) when rasterized directly at the target size. Supersampling and
    # downscaling with a quality filter blends those fringes back into neutral gray.
    supersample = 6
    raw_png = cairosvg.svg2png(url=str(path), output_width=width * supersample)
    rendered = Image.open(io.BytesIO(raw_png)).convert("RGBA")
    rendered = rendered.resize((width, round(rendered.height / supersample)), Image.LANCZOS)
    bg = Image.new("RGBA", rendered.size, background)
    bg.alpha_composite(rendered)
    return bg.convert("RGB")


def stack_images(images: list[Image.Image], width: int, margin: int, gap: int, output: Path, background: str) -> None:
    height = margin * 2 + sum(i.height for i in images) + gap * (len(images) - 1)
    canvas = Image.new("RGB", (width + margin * 2, height), background)
    y = margin
    for image in images:
        canvas.paste(image, (margin, y))
        y += image.height + gap
    canvas.save(output, optimize=True)


def generate_previews(profile: dict[str, Any]) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    for theme in ("light", "dark"):
        bg = THEMES[theme]["preview_bg"]
        desktop: list[Image.Image] = [
            render_svg(GENERATED/f"hero-desktop-{theme}.svg", 880, bg),
            render_svg(GENERATED/f"status-desktop-{theme}.svg", 880, bg),
        ]
        contact_row = Image.new("RGB", (880, 76), bg)
        for x, item in zip((0, 300, 600), profile["contacts"]):
            contact_row.paste(render_svg(GENERATED/f'contact-{item["label"].lower()}-desktop-{theme}.svg', 280, bg), (x, 0))
        desktop += [contact_row, render_svg(GENERATED/f"featured-desktop-{theme}.svg", 880, bg), render_svg(GENERATED/f"current-header-desktop-{theme}.svg", 880, bg)]
        current_cards = [render_svg(GENERATED/f"current-{i}-desktop-{theme}.svg", 425, bg) for i in range(len(profile["current"]))]
        for i in range(0, len(current_cards), 2):
            row = Image.new("RGB", (880, 108), bg)
            row.paste(current_cards[i], (0, 0))
            if i + 1 < len(current_cards):
                row.paste(current_cards[i + 1], (455, 0))
            desktop.append(row)
        desktop.append(render_svg(GENERATED/f"certifications-header-desktop-{theme}.svg", 880, bg))
        cert_row = Image.new("RGB", (880, 84), bg)
        cert_row.paste(render_svg(GENERATED/f"cert-0-desktop-{theme}.svg", 425, bg), (0, 0))
        cert_row.paste(render_svg(GENERATED/f"cert-1-desktop-{theme}.svg", 425, bg), (455, 0))
        desktop.append(cert_row)
        desktop.append(render_svg(GENERATED/f"statistics-header-desktop-{theme}.svg", 880, bg))
        desktop.append(render_svg(ROOT/profile["statistics"]["path"], 880, bg))
        stack_images(desktop, 880, 24, 12, DOCS/f"preview-desktop-{theme}.png", bg)

        mobile: list[Image.Image] = [
            render_svg(GENERATED/f"hero-mobile-{theme}.svg", 360, bg),
            render_svg(GENERATED/f"status-mobile-{theme}.svg", 360, bg),
        ]
        for item in profile["contacts"]:
            mobile.append(render_svg(GENERATED/f'contact-{item["label"].lower()}-mobile-{theme}.svg', 360, bg))
        mobile += [render_svg(GENERATED/f"featured-mobile-{theme}.svg", 360, bg), render_svg(GENERATED/f"current-header-mobile-{theme}.svg", 360, bg)]
        for i in range(len(profile["current"])):
            mobile.append(render_svg(GENERATED/f"current-{i}-mobile-{theme}.svg", 360, bg))
        mobile.append(render_svg(GENERATED/f"certifications-header-mobile-{theme}.svg", 360, bg))
        for i in range(len(profile["certifications"])):
            mobile.append(render_svg(GENERATED/f"cert-{i}-mobile-{theme}.svg", 360, bg))
        mobile.append(render_svg(GENERATED/f"statistics-header-mobile-{theme}.svg", 360, bg))
        mobile.append(render_svg(ROOT/profile["statistics"]["path"], 360, bg))
        stack_images(mobile, 360, 15, 10, DOCS/f"preview-mobile-{theme}.png", bg)



def update_contents() -> None:
    files = sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    (ROOT / "REPOSITORY-CONTENTS.txt").write_text("\n".join(files) + "\n", encoding="utf-8")


def save_generated(profile: dict[str, Any]) -> None:
    if GENERATED.exists():
        shutil.rmtree(GENERATED)
    GENERATED.mkdir(parents=True, exist_ok=True)
    for theme in ("light", "dark"):
        for mobile, layout in ((False, "desktop"), (True, "mobile")):
            outputs = {
                f"hero-{layout}-{theme}.svg": generate_hero(profile, mobile, theme),
                f"status-{layout}-{theme}.svg": generate_status(profile, mobile, theme),
                f"featured-{layout}-{theme}.svg": generate_featured(profile, mobile, theme),
                f"current-header-{layout}-{theme}.svg": generate_header("currently working on", mobile, theme),
                f"certifications-header-{layout}-{theme}.svg": generate_header("certifications", mobile, theme),
                f"statistics-header-{layout}-{theme}.svg": generate_header("github profile statistics", mobile, theme),
            }
            for item in profile["contacts"]:
                outputs[f'contact-{item["label"].lower()}-{layout}-{theme}.svg'] = generate_contact_card(item, mobile, theme)
            for i, item in enumerate(profile["current"]):
                outputs[f"current-{i}-{layout}-{theme}.svg"] = generate_current_card(item, mobile, theme)
            for i, item in enumerate(profile["certifications"]):
                outputs[f"cert-{i}-{layout}-{theme}.svg"] = generate_cert_card(item, mobile, theme)
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
