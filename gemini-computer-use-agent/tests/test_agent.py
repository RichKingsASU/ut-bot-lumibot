"""Unit tests for Gemini Computer Use Agent modules."""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import AgentConfig
from browser_env import denormalize_x, denormalize_y, is_url_permitted
from safety import SafetyManager



class TestComputerUseAgent(unittest.TestCase):

    def test_coordinate_denormalization(self):
        screen_w = 1440
        screen_h = 900

        self.assertEqual(denormalize_x(0, screen_w), 0)
        self.assertEqual(denormalize_x(500, screen_w), 720)
        self.assertEqual(denormalize_x(1000, screen_w), 1440)

        self.assertEqual(denormalize_y(0, screen_h), 0)
        self.assertEqual(denormalize_y(500, screen_h), 450)
        self.assertEqual(denormalize_y(1000, screen_h), 900)

    def test_domain_permission_validation(self):
        allowed = ["google.com", "wikipedia.org"]
        blocked = ["malicious.com"]

        # Permitted url
        ok, msg = is_url_permitted("https://www.google.com/search?q=test", allowed, blocked)
        self.assertTrue(ok)

        # Blocked url
        ok, msg = is_url_permitted("https://malicious.com/phish", allowed, blocked)
        self.assertFalse(ok)
        self.assertIn("blocked", msg)

        # Not in allowlist
        ok, msg = is_url_permitted("https://unallowed.org", allowed, blocked)
        self.assertFalse(ok)
        self.assertIn("allowed domains", msg)

    def test_config_defaults(self):
        config = AgentConfig()
        self.assertEqual(config.screen_width, 1440)
        self.assertEqual(config.screen_height, 900)
        self.assertEqual(config.model, "gemini-3.6-flash")
        self.assertTrue(config.headless)

    def test_safety_blocked_decision(self):
        mock_logger = MagicMock()
        safety_mgr = SafetyManager(logger=mock_logger)

        decision = {"decision": "blocked", "explanation": "Insecure operation"}
        status, ack = safety_mgr.process_safety_decision(decision)
        self.assertEqual(status, "HALT")
        self.assertFalse(ack)


if __name__ == "__main__":
    unittest.main()
