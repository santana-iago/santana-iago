#!/usr/bin/env python3
"""Run with: python scripts/test_build_profile.py"""
from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from build_profile import (
    generate_current_card,
    generate_hero,
    load_profile,
    responsive_linked_picture,
    responsive_picture,
    wrap_words,
)


class ProfileRenderingTests(unittest.TestCase):
    def test_picture_defaults_to_mobile_without_a_matching_source(self):
        for markup in (
            responsive_picture("status", "Status"),
            responsive_linked_picture("current-0", "Project", None),
        ):
            with self.subTest(markup=markup):
                self.assertRegex(markup, r'<img\s+src="[^"]+-mobile\.svg"')
                self.assertRegex(markup, r'<source\s+media="\(min-width: \d+px\)" srcset="[^"]+-desktop\.svg"')

    def test_hero_paints_its_own_background_in_both_palettes(self):
        svg = ET.fromstring(generate_hero(load_profile(), True, None))
        self.assertEqual(svg[1].tag, "{http://www.w3.org/2000/svg}rect")
        self.assertEqual(svg[1].attrib["class"], "surface")
        self.assertIn(".surface{fill:#ffffff}", svg[0].text)
        self.assertIn(".surface{fill:#0d1117}", svg[0].text)

    def test_mobile_project_shows_full_description(self):
        profile = load_profile()
        item = {**profile["current"][0], "description": (
            "Building a tool to monitor campus parking availability and help staff review "
            "occupancy across the car park throughout the day."
        )}
        svg = ET.fromstring(generate_current_card(item, True, "light"))
        descriptions = svg.findall(".//{*}text[@class='ui description-mobile']/{*}tspan")
        self.assertEqual(" ".join(line.text for line in descriptions), item["description"])


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
