#!/usr/bin/env python3
"""Run with: python scripts/test_build_profile.py"""
from __future__ import annotations

import copy
import unittest

from build_profile import ROOT, load_profile, load_translation, localize, validate_translation, wrap_words


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


class LocalizationTests(unittest.TestCase):
    """Guards the EN/PT-BR translation overlay: every card must be matched by
    its stable id (never by array position or by the translated text itself),
    and a missing/ambiguous/orphaned translation must fail the build loudly
    rather than silently falling back to English."""

    def setUp(self):
        self.profile = load_profile()
        self.translation = load_translation(ROOT / "profile.pt-BR.yml")

    def test_real_translation_file_validates_cleanly(self):
        validate_translation(self.profile, self.translation, "pt-BR")  # no raise

    def test_localize_preserves_structural_fields(self):
        localized = localize(self.profile, self.translation, "pt-BR")
        for section in ("featured", "current", "certifications"):
            for base_item, localized_item in zip(self.profile[section], localized[section]):
                self.assertEqual(base_item["id"], localized_item["id"])
                if "logo" in base_item:
                    self.assertEqual(base_item["logo"], localized_item["logo"])
                if "url" in base_item:
                    self.assertEqual(base_item.get("url"), localized_item.get("url"))

    def test_localize_translates_text_fields(self):
        localized = localize(self.profile, self.translation, "pt-BR")
        cyber = next(i for i in localized["featured"] if i["id"] == "cyber-security-iteam")
        self.assertEqual(cyber["title"], "Analista de Cybersecurity @ iT.EAM")

    def test_english_profile_is_returned_unmodified(self):
        # translation=None means "no overlay" (English) — must be a pure
        # passthrough, never a copy that could silently diverge from
        # profile.yml.
        self.assertIs(localize(self.profile, None, "en"), self.profile)

    def test_unknown_translation_id_is_rejected(self):
        broken = copy.deepcopy(self.translation)
        broken["featured"]["does-not-exist"] = broken["featured"]["criptoescape"]
        with self.assertRaises(ValueError):
            validate_translation(self.profile, broken, "pt-BR")

    def test_missing_card_translation_is_rejected(self):
        broken = copy.deepcopy(self.translation)
        del broken["current"]["pet-compet"]
        with self.assertRaises(ValueError):
            validate_translation(self.profile, broken, "pt-BR")

    def test_missing_required_field_is_rejected(self):
        broken = copy.deepcopy(self.translation)
        del broken["featured"]["criptoescape"]["description"]
        with self.assertRaises(ValueError):
            validate_translation(self.profile, broken, "pt-BR")

    def test_duplicate_profile_id_is_rejected(self):
        dup_profile = copy.deepcopy(self.profile)
        dup_profile["current"][1]["id"] = dup_profile["current"][0]["id"]
        with self.assertRaises(ValueError):
            validate_translation(dup_profile, self.translation, "pt-BR")

    def test_line_override_never_leaks_across_languages(self):
        # post-quantum-cryptography-research is the one card where EN sets
        # title_lines_desktop; its PT-BR translation must get its own value,
        # never inherit English's line breaks under a Portuguese title.
        localized = localize(self.profile, self.translation, "pt-BR")
        pqc_en = next(i for i in self.profile["current"] if i["id"] == "post-quantum-cryptography-research")
        pqc_pt = next(i for i in localized["current"] if i["id"] == "post-quantum-cryptography-research")
        self.assertNotEqual(pqc_en["title_lines_desktop"], pqc_pt["title_lines_desktop"])

        # chemical-products-platform has no title_lines_desktop in either
        # language — merging must not invent one.
        chem_pt = next(i for i in localized["current"] if i["id"] == "chemical-products-platform")
        self.assertNotIn("title_lines_desktop", chem_pt)


if __name__ == "__main__":
    unittest.main()
