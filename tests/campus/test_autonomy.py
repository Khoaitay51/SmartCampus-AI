"""Unit tests cho SAFETY_HITL_ENABLED (Full Autopilot vs Tiered Autonomy)."""
import os
import unittest
from unittest import mock

from app.campus.autonomy import decide_autonomy

ENV = "SAFETY_HITL_ENABLED"


class AutonomyDecisionTests(unittest.TestCase):
    def test_manual_hitl_always_pending(self):
        can_auto, status, notes, req_conf = decide_autonomy(
            "set_fan", 0.95, hitl_active=True, hitl_env=True
        )
        self.assertFalse(can_auto)
        self.assertEqual(status, "pending")
        self.assertIsNone(notes)
        self.assertTrue(req_conf)

    def test_tiered_autonomy_allows_tier1_high_conf_and_blocks_tier2(self):
        with mock.patch.dict(os.environ, {ENV: "true"}):
            # Tier-1 (set_fan) với conf=0.9 -> auto_approved
            can_auto, status, _, req_conf = decide_autonomy("set_fan", 0.9, hitl_active=False)
            self.assertTrue(can_auto)
            self.assertEqual(status, "auto_approved")
            self.assertFalse(req_conf)

            # Tier-1 với conf=0.6 (< 0.8) -> bị chặn về pending
            can_auto, status, _, req_conf = decide_autonomy("set_fan", 0.6, hitl_active=False)
            self.assertFalse(can_auto)
            self.assertEqual(status, "pending")
            self.assertTrue(req_conf)

            # Tier-2 (set_door, set_mode, trigger_buzzer) -> bị chặn về pending dù conf=0.99
            for tool in ("set_door", "set_mode", "trigger_buzzer"):
                with self.subTest(tool=tool):
                    can_auto, status, _, req_conf = decide_autonomy(tool, 0.99, hitl_active=False)
                    self.assertFalse(can_auto)
                    self.assertEqual(status, "pending")
                    self.assertTrue(req_conf)

    def test_full_autopilot_when_safety_hitl_env_disabled(self):
        with mock.patch.dict(os.environ, {ENV: "false"}):
            # M1 / M2 / M3: Khi SAFETY_HITL_ENABLED=false, cả Tier-2 lẫn conf thấp đều chạy Autopilot
            for tool, conf in (("set_door", 0.95), ("set_mode", 0.5), ("trigger_buzzer", 0.4), ("set_fan", 0.3)):
                with self.subTest(tool=tool, conf=conf):
                    can_auto, status, _, req_conf = decide_autonomy(tool, conf, hitl_active=False)
                    self.assertTrue(can_auto)
                    self.assertEqual(status, "auto_approved")
                    self.assertFalse(req_conf)


if __name__ == "__main__":
    unittest.main()

