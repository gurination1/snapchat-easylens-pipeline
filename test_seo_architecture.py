"""
Unit tests for Snapchat Lens Search SEO, Keyword Architecture & Tag Sanitization
Verifies compliance with Snapchat EasyLens V0 client rules, 18-char title limit, and viral SEO tags.
"""

import unittest
import re
import os
import sys

# Ensure local imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from easylens_api import EasyLensClient
from gemini_lens_agent import generate_lens_prompt, sanitize_lens_name, CHANNEL_PROMPT_MATRICES


class TestSnapchatLensSEO(unittest.TestCase):

    def test_easylens_tag_sanitization_rules(self):
        """Verify sanitize_tags matches EasyLens V0 client-side constraints and filters dev jargon."""
        raw_tags = [
            "Dragon Horns",      # Space should be stripped -> dragonhorns
            "Character",         # Clean
            "very_long_tag_name_that_exceeds_fifteen", # Sliced to 15 -> verylongtagnam
            "DRAGON",            # Lowercased -> dragon (duplicate of cleaned "dragon")
            "anime",             # Clean
            "cyber-punk!",       # Punctuation stripped -> cyberpunk
            "fantasy",           # Clean
            "pbr",               # Banned dev jargon -> filtered out
            "vfx",               # Banned dev jargon -> filtered out
            "mouthopen",         # Banned dev jargon -> filtered out
            "aesthetic",         # Clean viral tag
            "extra_tag_12"       # Should be dropped (max 8)
        ]

        cleaned = EasyLensClient.sanitize_tags(raw_tags)

        # 1. Max 8 tags
        self.assertLessEqual(len(cleaned), 8)
        self.assertGreaterEqual(len(cleaned), 5)

        # 2. Each tag <= 15 chars, alphanumeric only, lowercase
        for tag in cleaned:
            self.assertLessEqual(len(tag), 15)
            self.assertTrue(tag.isalnum(), f"Tag '{tag}' contains non-alphanumeric characters")
            self.assertEqual(tag, tag.lower(), f"Tag '{tag}' is not lowercase")

        # 3. Deduplication check
        self.assertEqual(len(cleaned), len(set(cleaned)))

        # 4. Check specific transformations & dev jargon exclusion
        self.assertIn("dragonhorns", cleaned)
        self.assertIn("character", cleaned)
        self.assertIn("verylongtagname", cleaned)
        self.assertIn("anime", cleaned)
        self.assertIn("cyberpunk", cleaned)
        self.assertNotIn("pbr", cleaned)
        self.assertNotIn("vfx", cleaned)
        self.assertNotIn("mouthopen", cleaned)

    def test_sanitize_lens_name_strict_18_chars(self):
        """Verify sanitize_lens_name prevents mid-word truncation and enforces <= 18 characters."""
        test_cases = [
            ("Baroque Heart Match", "Baroque Heart"),        # 19 chars -> cuts cleanly at word boundary
            ("Pastel Pandacorn Ears", "Pastel Pandacorn"),   # 21 chars -> cuts at word boundary
            ("Aether Dragon Crown", "Aether Dragon"),        # 19 chars -> cuts at word boundary
            ("Pearl Celestial Diadem", "Pearl Celestial"),   # 22 chars -> cuts at word boundary
            ("Zero-G Chrome Tesseract", "Zero-G Chrome"),     # 23 chars -> cuts cleanly
            ("Dragon Horns", "Dragon Horns"),                # 12 chars -> untouched
            ("Anime Ki Aura", "Anime Ki Aura"),              # 13 chars -> untouched
            ("Solar Flare Corona", "Solar Flare Corona")     # 18 chars -> untouched
        ]

        for raw_name, expected in test_cases:
            cleaned = sanitize_lens_name(raw_name, max_len=18)
            self.assertLessEqual(len(cleaned), 18, f"'{cleaned}' exceeds 18 chars limit")
            self.assertEqual(cleaned, expected, f"Expected '{expected}', got '{cleaned}'")
            self.assertFalse(cleaned.endswith("Matc"), f"Truncated syllable detected: '{cleaned}'")
            self.assertFalse(cleaned.endswith("Crow"), f"Truncated syllable detected: '{cleaned}'")

    def test_publish_payload_safe_title_and_tags(self):
        """Verify publish_lens payload includes enroll_in_payouts, safe title <=18 chars, and sanitized tags."""
        client = EasyLensClient()
        mock_payload = {}
        def mock_request(method, url, json=None, **kwargs):
            nonlocal mock_payload
            mock_payload = json
            class DummyRes:
                status_code = 200
                ok = True
                text = "{}"
                def raise_for_status(self): pass
                def json(self): return {"status": "success", "lens_central_lens_id": "test_id"}
            return DummyRes()

        client._request_with_retry = mock_request
        client.publish_lens(
            conversation_id="conv_123",
            lens_name="Baroque Heart Match Extra Words",
            tags=["Dragon", "Fantasy", "Horns", "3D", "PBR", "Anime", "VFX", "Glow", "Aesthetic"]
        )

        self.assertTrue(mock_payload.get("enroll_in_payouts"), "enroll_in_payouts MUST be True in publish payload")
        safe_name = mock_payload.get("lens_name")
        self.assertLessEqual(len(safe_name), 18, f"Published lens_name '{safe_name}' exceeds 18 chars")
        self.assertEqual(mock_payload.get("source_application"), "LensStudioWeb")
        self.assertTrue(mock_payload.get("remixable"))
        self.assertEqual(len(mock_payload.get("tags")), 8, "Tags MUST be capped at 8")
        for t in mock_payload.get("tags"):
            self.assertTrue(t.isalnum())
            self.assertEqual(t, t.lower())
            self.assertNotIn(t, ["pbr", "vfx", "mouthopen", "3d"])

    def test_gemini_lens_agent_seo_spec(self):
        """Verify prompt generator produces <= 18 char title and clean tags across accounts."""
        for acc in ["1", "2", "3", "4", "5"]:
            plan = generate_lens_prompt(account_id=acc)
            name = plan.get("lens_name", "")
            tags = plan.get("tags", [])

            self.assertLessEqual(len(name), 18, f"Account {acc} title '{name}' exceeds 18 characters")
            self.assertGreaterEqual(len(tags), 6, f"Account {acc} generated fewer than 6 tags: {tags}")
            self.assertLessEqual(len(tags), 8, f"Account {acc} generated more than 8 tags: {tags}")

            for t in tags:
                self.assertTrue(t.isalnum(), f"Account {acc} tag '{t}' is not strictly alphanumeric")
                self.assertEqual(t, t.lower(), f"Account {acc} tag '{t}' is not lowercase")
                self.assertLessEqual(len(t), 15, f"Account {acc} tag '{t}' exceeds 15 chars")
                self.assertNotIn(t, ["pbr", "vfx", "mouthopen", "mouth_open", "3d", "filigree", "diadem"])

    def test_all_channel_tag_pools_alphanumeric_and_zero_dev_jargon(self):
        """Verify all genre tag pools across channels contain zero underscores, zero dev jargon, and valid format."""
        banned = {"pbr", "vfx", "mouthopen", "mouth_open", "3d", "filigree", "diadem"}
        for ch_id, spec in CHANNEL_PROMPT_MATRICES.items():
            pool = spec.get("tag_pool", [])
            self.assertGreaterEqual(len(pool), 8, f"Channel {ch_id} tag pool has fewer than 8 tags")
            for t in pool:
                self.assertTrue(t.isalnum(), f"Channel {ch_id} tag pool contains invalid tag: '{t}'")
                self.assertEqual(t, t.lower())
                self.assertLessEqual(len(t), 15)
                self.assertNotIn(t, banned, f"Channel {ch_id} contains banned dev tag: '{t}'")


if __name__ == "__main__":
    unittest.main()
