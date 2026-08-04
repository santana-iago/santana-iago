#!/usr/bin/env python3
"""Run with: python scripts/test_build_profile.py"""
from __future__ import annotations

import unittest

from build_profile import wrap_words


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
