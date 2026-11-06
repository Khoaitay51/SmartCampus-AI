"""Unit tests cho SAFETY_FSM_ENABLED (Global Tool Mode) tại AI Backend."""
import os
import unittest
from unittest import mock

from app.fallback.rules import is_tool_allowed_in_mode as rules_is_allowed
from app.tools.registry import is_tool_allowed_in_mode as registry_is_allowed

ENV = "SAFETY_FSM_ENABLED"


class BackendFsmToggleTests(unittest.TestCase):
    def test_rules_blocks_restricted_tools_when_fsm_enabled(self):
        with mock.patch.dict(os.environ, {ENV: "true"}):
            self.assertFalse(rules_is_allowed("EXAM", "set_door"))
            self.assertFalse(rules_is_allowed("EXAM", "trigger_buzzer"))
            self.assertFalse(rules_is_allowed("LOCK", "set_fan"))
            self.assertFalse(rules_is_allowed("LOCK", "set_door"))
            self.assertFalse(registry_is_allowed("set_door", "EXAM"))
            self.assertFalse(registry_is_allowed("trigger_buzzer", "EXAM"))
            self.assertFalse(registry_is_allowed("set_fan", "LOCK"))

    def test_rules_allows_all_tools_globally_when_fsm_disabled(self):
        with mock.patch.dict(os.environ, {ENV: "false"}):
            for mode in ("EXAM", "LOCK", "SUSPECTED", "EMERGENCY", "UNKNOWN"):
                for tool in ("set_door", "set_fan", "trigger_buzzer", "set_led", "set_mode", "send_alert"):
                    with self.subTest(mode=mode, tool=tool):
                        self.assertTrue(rules_is_allowed(mode, tool))
                        self.assertTrue(registry_is_allowed(tool, mode))


if __name__ == "__main__":
    unittest.main()
