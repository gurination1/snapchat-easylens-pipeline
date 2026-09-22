#!/usr/bin/env python3
"""
Unit test suite for Snapchat Fleet Autonomous Pacing & 3x Daily Quota Resolver.
Verifies rolling 24h quotas, 6.0h minimum cooldown, catch-up priority, and idle resting.
"""

import os
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from resolve_target_account import resolve_fleet_target


class TestPacingQuota(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.temp_file = tempfile.NamedTemporaryFile("w", delete=False)
        self.history_file = self.temp_file.name
        self.temp_file.close()

    def tearDown(self):
        if os.path.exists(self.history_file):
            os.unlink(self.history_file)

    def write_history(self, history):
        with open(self.history_file, "w") as f:
            json.dump(history, f)

    def test_forced_account(self):
        decision = resolve_fleet_target(
            history_file=self.history_file,
            forced_account="4"
        )
        self.assertEqual(decision["account_id"], "4")
        self.assertTrue(decision["should_run"])

    def test_empty_history_selects_account(self):
        self.write_history([])
        decision = resolve_fleet_target(
            history_file=self.history_file,
            min_cooldown_hours=6.0,
            max_daily_posts=3
        )
        self.assertIn(decision["account_id"], ["1", "2", "3", "4", "5"])
        self.assertTrue(decision["should_run"])
        self.assertEqual(decision["posts_24h"], 0)

    def test_all_accounts_at_daily_quota(self):
        fake_hist = []
        for aid in ["1", "2", "3", "4", "5"]:
            for h_ago in [2.0, 8.0, 14.0]:
                t = (self.now - timedelta(hours=h_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
                fake_hist.append({"account_id": aid, "timestamp": t})
        self.write_history(fake_hist)

        decision = resolve_fleet_target(
            history_file=self.history_file,
            min_cooldown_hours=6.0,
            max_daily_posts=3
        )
        self.assertFalse(decision["should_run"])
        self.assertIn("completed their 3x daily quota", decision["reason"])

    def test_catch_up_prioritization(self):
        fake_hist = [
            # Account 1: 1 post 8h ago (eligible)
            {"account_id": "1", "timestamp": (self.now - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")},
            # Account 2: 2 posts (eligible, last 8h ago)
            {"account_id": "2", "timestamp": (self.now - timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ")},
            {"account_id": "2", "timestamp": (self.now - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")},
            # Account 3: 3 posts (capped)
            {"account_id": "3", "timestamp": (self.now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")},
            {"account_id": "3", "timestamp": (self.now - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")},
            {"account_id": "3", "timestamp": (self.now - timedelta(hours=6.5)).strftime("%Y-%m-%dT%H:%M:%SZ")},
            # Account 4: 0 posts in 24h (old post 30h ago)
            {"account_id": "4", "timestamp": (self.now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")},
            # Account 5: 1 post 20h ago (eligible)
            {"account_id": "5", "timestamp": (self.now - timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%SZ")},
        ]
        self.write_history(fake_hist)

        decision = resolve_fleet_target(
            history_file=self.history_file,
            min_cooldown_hours=6.0,
            max_daily_posts=3
        )
        self.assertTrue(decision["should_run"])
        # Account 4 has 0 posts in 24h -> must be prioritized over accounts with 1 or 2 posts
        self.assertEqual(decision["account_id"], "4")
        self.assertEqual(decision["posts_24h"], 0)

    def test_cooldown_holding(self):
        fake_hist = [
            {"account_id": "1", "timestamp": (self.now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")},
            {"account_id": "2", "timestamp": (self.now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")},
            {"account_id": "3", "timestamp": (self.now - timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ")},
            {"account_id": "4", "timestamp": (self.now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")},
            {"account_id": "5", "timestamp": (self.now - timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")},
        ]
        self.write_history(fake_hist)

        decision = resolve_fleet_target(
            history_file=self.history_file,
            min_cooldown_hours=6.0,
            max_daily_posts=3
        )
        # All accounts posted < 6.0h ago -> should hold cleanly
        self.assertFalse(decision["should_run"])
        # Next eligible should be Account 5 (idle 5h, needs 1h more)
        self.assertEqual(decision["account_id"], "5")
        self.assertIn("cooldown", decision["reason"].lower())


if __name__ == "__main__":
    unittest.main()
