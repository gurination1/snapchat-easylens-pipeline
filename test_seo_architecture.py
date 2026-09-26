"""
Unit tests for Snapchat Lens Search SEO, Keyword Architecture & Tag Sanitization
Verifies compliance with Snapchat EasyLens V0 client rules and 3-Tier SEO Framework.
"""

import unittest
import re
import os
import sys

# Ensure local imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from easylens_api import EasyLensClient
from gemini_lens_agent import generate_lens_prompt, CHANNEL_PROMPT_MATRICES
from pipeline_runner import STATIC_FALLBACKS


class TestSnapchatLensSEO(unittest.TestCase):

    def test_easylens_tag_sanitization_rules(self):
        """Verify sanitize_tags matches EasyLens V0 client-side constraints exactly."""
        raw_tags = [
            "Dragon Horns",      # Space should be stripped -> dragonhorns
            "3D-Character",      # Hyphen stripped -> 3dcharacter
            "very_long_tag_name_that_exceeds_fifteen", # Sliced to 15 -> verylongtagnam
            "DRAGON",            # Lowercased -> dragon (duplicate of cleaned "dragon")
            "anime",             # Clean
            "cyber-punk!",       # Punctuation stripped -> cyberpunk
            "fantasy",           # Clean
            "pbr",               # Clean
            "extra_tag_9",       # Should be dropped (max 8)
            "extra_tag_10"       # Should be dropped (max 8)
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

        # 4. Check specific transformations
        self.assertIn("dragonhorns", cleaned)
        self.assertIn("3dcharacter", cleaned)
        self.assertIn("verylongtagname", cleaned)
        self.assertIn("anime", cleaned)
        self.assertIn("cyberpunk", cleaned)

    def test_publish_payload_instant_payouts(self):
        """Verify publish_lens payload includes enroll_in_payouts and sanitized tags."""
        client = EasyLensClient()
        # Mock session to inspect prepared request
        mock_payload = {}
        def mock_request(method, url, json=None, **kwargs):
            nonlocal mock_payload
            mock_payload = json
            class DummyRes:
                status_code = 200
                def raise_for_status(self): pass
                def json(self): return {"status": "success", "lens_central_lens_id": "test_id"}
            return DummyRes()

        client._request_with_retry = mock_request
        client.publish_lens(
            conversation_id="conv_123",
            lens_name="Dragon Horns 3D",
            tags=["Dragon", "Fantasy", "Horns", "3D", "PBR", "Anime", "VFX", "Glow", "Excess"]
        )

        self.assertTrue(mock_payload.get("enroll_in_payouts"), "enroll_in_payouts MUST be True in publish payload")
        self.assertEqual(mock_payload.get("lens_name"), "Dragon Horns 3D")
        self.assertEqual(mock_payload.get("source_application"), "LensStudioWeb")
        self.assertTrue(mock_payload.get("remixable"))
        self.assertEqual(len(mock_payload.get("tags")), 8, "Tags MUST be capped at 8")
        for t in mock_payload.get("tags"):
            self.assertTrue(t.isalnum())
            self.assertEqual(t, t.lower())

    def test_gemini_lens_agent_seo_spec(self):
        """Verify prompt generator produces 8-tag SEO output with alphanumeric tokens."""
        for acc in ["1", "2", "3", "4", "5"]:
            plan = generate_lens_prompt(account_id=acc)
            tags = plan.get("tags", [])
            self.assertGreaterEqual(len(tags), 6, f"Account {acc} generated fewer than 6 tags: {tags}")
            self.assertLessEqual(len(tags), 8, f"Account {acc} generated more than 8 tags: {tags}")

            for t in tags:
                self.assertTrue(t.isalnum(), f"Account {acc} tag '{t}' is not strictly alphanumeric")
                self.assertEqual(t, t.lower(), f"Account {acc} tag '{t}' is not lowercase")
                self.assertLessEqual(len(t), 15, f"Account {acc} tag '{t}' exceeds 15 chars")

    def test_all_channel_tag_pools_alphanumeric(self):
        """Verify all genre tag pools across 5 accounts contain zero underscores or invalid chars."""
        for ch_id, spec in CHANNEL_PROMPT_MATRICES.items():
            pool = spec.get("tag_pool", [])
            self.assertGreaterEqual(len(pool), 8, f"Channel {ch_id} tag pool has fewer than 8 tags")
            for t in pool:
                self.assertTrue(t.isalnum(), f"Channel {ch_id} tag pool contains invalid tag: '{t}'")
                self.assertEqual(t, t.lower())
                self.assertLessEqual(len(t), 15)


if __name__ == "__main__":
    unittest.main()
