#!/usr/bin/env python3
"""Run with: python scripts/test_build_profile.py"""
from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from build_profile import (
    generate_current_card,
    generate_hero,
    load_profile,
    responsive_picture,
    wrap_words,
)


class ProfileRenderingTests(unittest.TestCase):
    def test_picture_defaults_to_mobile_without_a_matching_source(self):
        for url in (
            None,
            "https://example.com/project",
        ):
            markup = responsive_picture("current-0", "Project", url)
            for theme in ("light", "dark"):
                with self.subTest(url=url, theme=theme):
                    marker = f"#gh-{theme}-mode-only"
                    self.assertRegex(markup, rf'<img\s+src="[^"]+-mobile-{theme}\.svg{marker}"')
                    self.assertRegex(markup, rf'<source\s+media="\(min-width: \d+px\)" srcset="[^"]+-desktop-{theme}\.svg{marker}"')

    def test_picture_only_links_to_a_page_when_a_destination_is_configured(self):
        decorative = responsive_picture("current-0", "Project")
        linked = responsive_picture("current-0", "Project", "https://example.com/project")
        for theme in ("light", "dark"):
            with self.subTest(theme=theme):
                marker = f"#gh-{theme}-mode-only"
                self.assertIn(f'<a href="{marker}" tabindex="-1"><picture>', decorative)
                self.assertIn(f'<a href="https://example.com/project{marker}"><picture>', linked)

    def test_hero_paints_its_own_background_with_a_fixed_palette(self):
        for theme, color in [("light", "#ffffff"), ("dark", "#0d1117")]:
            with self.subTest(theme=theme):
                svg = ET.fromstring(generate_hero(load_profile(), True, theme))
                self.assertEqual(svg[1].tag, "{http://www.w3.org/2000/svg}rect")
                self.assertEqual(svg[1].attrib["class"], "surface")
                self.assertIn(f".surface{{fill:{color}}}", svg[0].text)
                self.assertNotIn("prefers-color-scheme", svg[0].text)

    def test_mobile_project_shows_full_description(self):
        profile = load_profile()
        item = {**profile["current"][0], "description": (
            "Building a tool to monitor campus parking availability and help staff review "
            "occupancy across the car park throughout the day."
        )}
        svg = ET.fromstring(generate_current_card(item, True, "light"))
        descriptions = svg.findall(".//{*}text[@class='ui description-mobile']/{*}tspan")
        self.assertEqual(" ".join(line.text for line in descriptions), item["description"])

    def test_extended_project_description_fits_in_both_layouts_and_themes(self):
        item = next(
            item for item in load_profile()["current"]
            if item.get("generated_name") == "current-salamanca"
        )
        for mobile in (False, True):
            for theme in ("light", "dark"):
                with self.subTest(mobile=mobile, theme=theme):
                    svg = ET.fromstring(generate_current_card(item, mobile, theme))
                    description_class = "ui description-mobile" if mobile else "ui description"
                    description = svg.find(f".//{{*}}text[@class='{description_class}']")
                    self.assertEqual(" ".join(line.text for line in description), item["description"])
                    image = svg.find("{*}image")
                    self.assertEqual(float(image.attrib["width"]), 44)
                    self.assertEqual(float(image.attrib["height"]), 44)


class WrapWordsTests(unittest.TestCase):
    def test_short_text_fits_on_one_line(self):
        lines = wrap_words("Short line.", max_chars=35, max_lines=3)
        self.assertEqual(lines, ["Short line."])

    def test_text_that_exactly_fits_available_lines_is_not_truncated(self):
        # Regression test for the mobile "featured work" card that used to
        # lose its final word ("investigations.") to a silent ellipsis.
        text = "Turning telemetry into actionable intelligence, stronger detections and faster investigations."
        lines = wrap_words(text, max_chars=35, max_lines=3)
        self.assertLessEqual(len(lines), 3)
        self.assertNotIn("…", "".join(lines))
        self.assertTrue(" ".join(lines).endswith("investigations."))

    def test_overflowing_text_is_truncated_with_single_ellipsis(self):
        text = "One two three four five six seven eight nine ten eleven twelve thirteen fourteen"
        lines = wrap_words(text, max_chars=10, max_lines=2)
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[-1].endswith("…"))
        self.assertEqual(lines[-1].count("…"), 1)

    def test_truncation_does_not_leave_trailing_space_or_period_before_ellipsis(self):
        text = "alpha beta gamma delta epsilon."
        lines = wrap_words(text, max_chars=6, max_lines=1)
        self.assertTrue(lines[-1].endswith("…"))
        self.assertFalse(lines[-1].endswith(" …"))
        self.assertFalse(lines[-1].endswith(". …"))

    def test_single_word_longer_than_max_chars_is_kept_whole(self):
        lines = wrap_words("Supercalifragilisticexpialidocious", max_chars=10, max_lines=3)
        self.assertEqual(lines, ["Supercalifragilisticexpialidocious"])

    def test_empty_string_returns_single_empty_line(self):
        self.assertEqual(wrap_words("", max_chars=35, max_lines=3), [""])

    def test_never_exceeds_max_lines(self):
        text = " ".join(["word"] * 50)
        lines = wrap_words(text, max_chars=10, max_lines=3)
        self.assertLessEqual(len(lines), 3)


if __name__ == "__main__":
    unittest.main()
