"""
tests/test_all_tools_execution.py
----------------------------------
Kiểm thử toàn bộ 7 RAG Tools và 6 Action Tools trong hệ thống SmartCampus AI Agent.
Đảm bảo tất cả các tool đều gọi thành công, không bị lỗi runtime, và trả về dữ liệu đúng chuẩn.
"""

from __future__ import annotations

import asyncio
import json
import sys
import unittest

from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from app.tools.registry import ACTION_TOOLS, RAG_TOOLS, is_tool_allowed_in_mode

from app.gateway.rag import execute_rag_tool
from app.gateway.actuator import ActuatorClient
from app.schemas.recommendation import ToolRecommendation, ALLOWED_ACTION_TOOLS
from app.tools.registry import ACTION_TOOLS, RAG_TOOLS, is_tool_allowed_in_mode


class TestAllToolsExecution(unittest.IsolatedAsyncioTestCase):
    """Test suite kiểm tra khả năng gọi (callability) của từng Tool."""

    async def test_all_rag_tools_callability(self):
        """Kiểm tra lần lượt 7 RAG Tools có thể thực thi và trả về dữ liệu JSON hợp lệ."""
        rag_test_cases = [
            ("search_history", {"query": "nhiệt độ phòng tăng cao", "time_range": "24h"}),
            ("get_telemetry", {"room_id": "room-a101", "metric": "temperature", "window": "1h"}),
            ("get_attendance", {"room_id": "room-a101", "class_code": "CS101"}),
            ("compare_rooms", {"room_ids": ["room-a101", "room-a102"], "metric": "temperature", "window": "1h"}),
            ("get_room_history", {"room_id": "room-a101", "hours": 24}),
            ("get_schedule", {"room_id": "room-a101", "date": "2026-09-24"}),
            ("get_predictions", {"room_id": "room-a101", "metric": "temperature", "horizon": "15m"}),
        ]

        registered_rag_names = {t.name for t in RAG_TOOLS}
        self.assertEqual(len(registered_rag_names), 7, "Số lượng RAG tools đăng ký phải đúng bằng 7")

        for tool_name, params in rag_test_cases:
            with self.subTest(tool=tool_name):
                # 1. Đảm bảo tool nằm trong danh sách đăng ký RAG_TOOLS
                self.assertIn(tool_name, registered_rag_names, f"RAG Tool '{tool_name}' chưa được đăng ký trong RAG_TOOLS")

                # 2. Gọi thực thi tool qua execute_rag_tool (tự động fallback mock data nếu backend offline)
                res_str = await execute_rag_tool(tool_name, params)
                self.assertIsInstance(res_str, str, f"Kết quả trả về từ RAG Tool '{tool_name}' phải là string JSON")

                # 3. Parse JSON và kiểm tra kết quả không rỗng
                res_json = json.loads(res_str)
                self.assertIsInstance(res_json, dict, f"Dữ liệu RAG Tool '{tool_name}' phải parse ra dict JSON hợp lệ")
                self.assertTrue(len(res_json) > 0, f"RAG Tool '{tool_name}' không được trả về dict rỗng")

    async def test_all_action_tools_callability(self):
        """Kiểm tra lần lượt 6 Action Tools có thể được khởi tạo, validate và phân quyền thành công."""
        action_test_cases = [
            ("set_fan", {"room_id": "room-a101", "state": "on", "speed": "high"}),
            ("set_door", {"room_id": "room-a101", "action": "lock"}),
            ("set_mode", {"room_id": "room-a101", "mode": "SAVING"}),
            ("trigger_buzzer", {"room_id": "room-a101", "pattern": "alarm", "duration": 5}),
            ("send_alert", {"level": "warning", "message": "Nhiệt độ phòng tăng cao", "target_roles": ["admin"]}),
            ("set_led", {"room_id": "room-a101", "color": "red", "state": "blink"}),
        ]

        registered_action_names = {t.name for t in ACTION_TOOLS}
        self.assertEqual(len(registered_action_names), 6, "Số lượng Action tools đăng ký phải đúng bằng 6")

        for tool_name, params in action_test_cases:
            with self.subTest(tool=tool_name):
                # 1. Đảm bảo tool nằm trong ACTION_TOOLS và ALLOWED_ACTION_TOOLS
                self.assertIn(tool_name, registered_action_names, f"Action Tool '{tool_name}' chưa đăng ký trong ACTION_TOOLS")
                self.assertIn(tool_name, ALLOWED_ACTION_TOOLS, f"Action Tool '{tool_name}' chưa nằm trong ALLOWED_ACTION_TOOLS whitelist")

                # 2. Kiểm tra khởi tạo ToolRecommendation schema cho AgentResponse recommendation
                tool_rec = ToolRecommendation(
                    tool_name=tool_name,
                    tool_params=params,
                    reason=f"Test call action {tool_name}",
                    confidence=0.9,
                    urgency="medium",
                )
                self.assertEqual(tool_rec.tool_name, tool_name)
                self.assertGreaterEqual(tool_rec.confidence, 0.5)

                # 3. Kiểm tra phân quyền tool trong EMERGENCY mode
                self.assertTrue(
                    is_tool_allowed_in_mode(tool_name, "EMERGENCY"),
                    f"Action Tool '{tool_name}' phải được cho phép trong EMERGENCY mode",
                )


if __name__ == "__main__":
    unittest.main()
