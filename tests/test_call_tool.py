"""
tests/test_call_tool.py
-----------------------
Kiểm thử danh sách đăng ký Tool (RAG Tools & Action Tools)
và Ma trận phân quyền theo Room Mode.
"""
from __future__ import annotations

import unittest
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from app.tools.registry import ACTION_TOOLS, RAG_TOOLS, is_tool_allowed_in_mode

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
        """Kiểm tra ma trận phân quyền room_mode từ app/tools/registry.py."""
        # SAVING mode: Cho phép set_fan, set_door, set_mode, send_alert, set_led (không trigger_buzzer)
        for tool in ["set_fan", "set_door", "set_mode", "send_alert", "set_led"]:
            self.assertTrue(is_tool_allowed_in_mode(tool, "SAVING"))
        self.assertFalse(is_tool_allowed_in_mode("trigger_buzzer", "SAVING"))

        # EXAM mode: Không tự ý set_door / trigger_buzzer trong giờ thi
        self.assertFalse(is_tool_allowed_in_mode("set_door", "EXAM"))
        self.assertFalse(is_tool_allowed_in_mode("trigger_buzzer", "EXAM"))
        self.assertTrue(is_tool_allowed_in_mode("set_fan", "EXAM"))
        self.assertTrue(is_tool_allowed_in_mode("send_alert", "EXAM"))
        self.assertTrue(is_tool_allowed_in_mode("set_mode", "EXAM"))
        self.assertTrue(is_tool_allowed_in_mode("set_led", "EXAM"))

        # LOCK mode: Giữ nguyên khóa cửa (cho phép send_alert, trigger_buzzer, set_mode)
        self.assertTrue(is_tool_allowed_in_mode("send_alert", "LOCK"))
        self.assertTrue(is_tool_allowed_in_mode("trigger_buzzer", "LOCK"))
        self.assertTrue(is_tool_allowed_in_mode("set_mode", "LOCK"))
        self.assertFalse(is_tool_allowed_in_mode("set_fan", "LOCK"))
        self.assertFalse(is_tool_allowed_in_mode("set_door", "LOCK"))
        self.assertFalse(is_tool_allowed_in_mode("set_led", "LOCK"))

        # SUSPECTED mode: set_fan, send_alert, set_led, trigger_buzzer, set_mode (không set_door)
        self.assertTrue(is_tool_allowed_in_mode("set_fan", "SUSPECTED"))
        self.assertTrue(is_tool_allowed_in_mode("send_alert", "SUSPECTED"))
        self.assertTrue(is_tool_allowed_in_mode("set_led", "SUSPECTED"))
        self.assertTrue(is_tool_allowed_in_mode("trigger_buzzer", "SUSPECTED"))
        self.assertTrue(is_tool_allowed_in_mode("set_mode", "SUSPECTED"))
        self.assertFalse(is_tool_allowed_in_mode("set_door", "SUSPECTED"))

        # EMERGENCY mode: Cho phép tất cả 6 action tools
        for tool in ["set_fan", "set_door", "set_mode", "trigger_buzzer", "send_alert", "set_led"]:
            self.assertTrue(is_tool_allowed_in_mode(tool, "EMERGENCY"))


if __name__ == "__main__":
    unittest.main()
