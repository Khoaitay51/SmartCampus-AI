"""
tests/test_call_tool.py
-----------------------
Kiểm thử danh sách đăng ký Tool (RAG Tools & Action Tools)
và Ma trận phân quyền theo Room Mode.
"""
from __future__ import annotations

import unittest

from app.tools.registry import (
    ACTION_TOOLS,
    RAG_TOOLS,
    is_tool_allowed_in_mode,
)


class TestToolsAndPermissions(unittest.TestCase):
    """Kiểm thử danh sách tool đăng ký và ma trận phân quyền room mode."""

    def test_registered_tools_count(self):
        """Đảm bảo danh sách tool đăng ký đủ 7 RAG Tools và 6 Action Tools."""
        self.assertEqual(len(RAG_TOOLS), 7)
        self.assertEqual(len(ACTION_TOOLS), 6)

        action_names = {t.name for t in ACTION_TOOLS}
        expected_actions = {"set_fan", "set_door", "set_mode", "trigger_buzzer", "send_alert", "set_led"}
        self.assertEqual(action_names, expected_actions)

    def test_permission_matrix_rules(self):
        """Kiểm tra ma trận phân quyền room_mode từ ảnh thiết kế của người dùng."""
        # SAVING mode: Cho phép tất cả 6 action tools
        for tool in ["set_fan", "set_door", "set_mode", "trigger_buzzer", "send_alert", "set_led"]:
            self.assertTrue(is_tool_allowed_in_mode(tool, "SAVING"))

        # EXAM mode: set_door KHÔNG được phép (No*)
        self.assertFalse(is_tool_allowed_in_mode("set_door", "EXAM"))
        self.assertTrue(is_tool_allowed_in_mode("set_fan", "EXAM"))
        self.assertTrue(is_tool_allowed_in_mode("send_alert", "EXAM"))

        # LOCK mode: Chỉ duy nhất send_alert được phép
        self.assertTrue(is_tool_allowed_in_mode("send_alert", "LOCK"))
        self.assertFalse(is_tool_allowed_in_mode("set_fan", "LOCK"))
        self.assertFalse(is_tool_allowed_in_mode("set_door", "LOCK"))
        self.assertFalse(is_tool_allowed_in_mode("set_mode", "LOCK"))
        self.assertFalse(is_tool_allowed_in_mode("trigger_buzzer", "LOCK"))
        self.assertFalse(is_tool_allowed_in_mode("set_led", "LOCK"))

        # SUSPECTED mode: set_fan (Yes), set_door (Yes), trigger_buzzer (Yes), send_alert (Yes), set_mode (No), set_led (No)
        self.assertTrue(is_tool_allowed_in_mode("set_fan", "SUSPECTED"))
        self.assertTrue(is_tool_allowed_in_mode("set_door", "SUSPECTED"))
        self.assertTrue(is_tool_allowed_in_mode("trigger_buzzer", "SUSPECTED"))
        self.assertTrue(is_tool_allowed_in_mode("send_alert", "SUSPECTED"))
        self.assertFalse(is_tool_allowed_in_mode("set_mode", "SUSPECTED"))
        self.assertFalse(is_tool_allowed_in_mode("set_led", "SUSPECTED"))

        # EMERGENCY mode: set_door (Yes), trigger_buzzer (Yes), send_alert (Yes), set_fan (No), set_mode (No), set_led (No)
        self.assertTrue(is_tool_allowed_in_mode("set_door", "EMERGENCY"))
        self.assertTrue(is_tool_allowed_in_mode("trigger_buzzer", "EMERGENCY"))
        self.assertTrue(is_tool_allowed_in_mode("send_alert", "EMERGENCY"))
        self.assertFalse(is_tool_allowed_in_mode("set_fan", "EMERGENCY"))
        self.assertFalse(is_tool_allowed_in_mode("set_mode", "EMERGENCY"))
        self.assertFalse(is_tool_allowed_in_mode("set_led", "EMERGENCY"))


if __name__ == "__main__":
    unittest.main()
