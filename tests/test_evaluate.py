"""
tests/test_evaluate.py
----------------------
Bộ kiểm thử tự động xác minh kết nối và khả năng thực thi nhiệm vụ
của file evaluate.py và ReActXenAgent.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException

import app.api.evaluate as evaluate_module
from app.api.evaluate import evaluate_event, get_agent
from app.agent.agent import ReActXenAgent
from app.gateway.rag import execute_rag_tool
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload
from app.schemas.recommendation import AgentResponse
from app.tools.registry import (
    ACTION_TOOLS,
    FINISH_TOOL,
    RAG_TOOLS,
    is_tool_allowed_in_mode,
    render_tool_desc,
)


class MockLLM:
    """Mock LLM thực thi protocol complete() cho ReAct / Review / Reflect."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = list(responses or [])
        self.call_history: list[str] = []

    async def complete(self, prompt: str) -> str:
        self.call_history.append(prompt)
        if self.responses:
            return self.responses.pop(0)
        # Default response: finish
        return (
            'Self-Ask: Cần làm gì tiếp theo?\n'
            'Thought: Đã đủ thông tin để kết luận.\n'
            'Action: finish\n'
            'Action Input: {"final_json": {"skip": true, "skip_reason": "default_mock_finish", "analysis": "Mock analysis hoàn tất."}}'
        )


def make_sample_payload(room_mode: str = "LECTURE") -> dict:
    """Tạo payload mẫu hợp lệ chuẩn EventPayload & OperationalContext."""
    room_id = str(uuid4())
    event_id = str(uuid4())
    return {
        "event_id": event_id,
        "event_type": "temperature_anomaly",
        "room_id": room_id,
        "timestamp": "2026-09-10T21:00:00Z",
        "event_data": {"measured_temp": 32.5},
        "operational_context": {
            "room": {
                "room_id": room_id,
                "room_name": "Phòng A101",
                "room_type": "lecture_hall",
                "current_mode": room_mode,
                "smoke_state": "normal",
            },
            "telemetry_summary": {
                "window_start": "2026-09-10T20:00:00Z",
                "window_end": "2026-09-10T21:00:00Z",
                "temperature": {"min": 24.0, "max": 32.5, "avg": 28.0, "latest": 32.5},
                "humidity": {"min": 50.0, "max": 65.0, "avg": 58.0, "latest": 60.0},
                "co2": {"min": 400.0, "max": 800.0, "avg": 600.0, "latest": 720.0},
                "smoke_value": {"min": 0.0, "max": 0.05, "avg": 0.01, "latest": 0.02},
                "air_quality": {"min": 70.0, "max": 95.0, "avg": 85.0, "latest": 88.0},
            },
            "occupancy": {
                "current_count": 45,
                "total_in": 50,
                "total_out": 5,
                "trend": "phong hoc",
            },
            "active_session": None,
            "recent_events": [],
        },
    }


class TestEvaluateAndAgent(unittest.IsolatedAsyncioTestCase):
    """Kiểm thử kết nối và thực thi giữa evaluate.py và ReActXenAgent."""

    def test_imports_and_definitions(self):
        """Kiểm tra các module cốt lõi được import và khởi tạo bình thường."""
        self.assertTrue(hasattr(evaluate_module, "evaluate_event"))
        self.assertTrue(hasattr(evaluate_module, "get_agent"))
        self.assertGreater(len(RAG_TOOLS), 0)
        self.assertGreater(len(ACTION_TOOLS), 0)
        self.assertEqual(FINISH_TOOL.name, "finish")

        # Kiểm tra khởi tạo agent
        agent = get_agent()
        self.assertIsInstance(agent, ReActXenAgent)

    def test_tools_registry_helpers(self):
        """Kiểm tra render mô tả tool và ma trận phân quyền."""
        desc = render_tool_desc(ACTION_TOOLS)
        self.assertIn("set_fan", desc)
        self.assertIn("trigger_buzzer", desc)

        # Quyền hạn chế trong giờ thi (EXAM)
        self.assertFalse(is_tool_allowed_in_mode("set_door", "EXAM"))
        self.assertTrue(is_tool_allowed_in_mode("set_fan", "EXAM"))

        # Quyền trong chế độ khẩn cấp (EMERGENCY)
        self.assertTrue(is_tool_allowed_in_mode("set_door", "EMERGENCY"))
        self.assertTrue(is_tool_allowed_in_mode("trigger_buzzer", "EMERGENCY"))

    async def test_execute_rag_tool_fallback(self):
        """Kiểm tra execute_rag_tool bắt lỗi an toàn khi backend chưa chạy."""
        # Gọi tool với params mẫu
        obs = await execute_rag_tool("get_telemetry", {"room_id": "test", "metric": "temperature", "window": "15m"})
        self.assertIsInstance(obs, str)
        # Kết quả trả về chuỗi thông báo lỗi an toàn thay vì ném exception làm sập tiến trình
        self.assertTrue(len(obs) > 0)

    async def test_evaluate_event_successful_execution(self):
        """Kiểm tra thực thi hoàn chỉnh /evaluate từ đầu vào -> Agent ReAct -> Review -> AgentResponse."""
        payload = make_sample_payload(room_mode="LECTURE")
        event_id = payload["event_id"]
        room_id = payload["room_id"]

        # Chuẩn bị phản hồi của LLM:
        # Bước 1 (ReAct): Agent kết luận với Finish action và đề xuất set_fan
        react_step_output = (
            f'Self-Ask: Nhiệt độ phòng đang cao, có nên bật quạt?\n'
            f'Thought: Nhiệt độ đo được là 32.5 độ, cần bật quạt thông gió.\n'
            f'Action: finish\n'
            f'Action Input: {{"final_json": {{"event_id": "{event_id}", "recommendation": {{"tool_name": "set_fan", "tool_params": {{"room_id": "{room_id}", "state": "on"}}, "reason": "Nhiệt độ phòng tăng cao", "confidence": 0.85, "urgency": "medium"}}, "analysis": "Nhiệt độ phòng tăng trong giờ học, đề xuất bật quạt làm mát.", "skip": false}}}}'
        )
        # Bước 2 (Review): Reviewer đánh giá Accomplished
        review_output = json.dumps({
            "status": "Accomplished",
            "reasoning": "Đề xuất hợp lý, đúng quyền hạn trong mode LECTURE.",
            "suggestions": None,
        })

        mock_llm = MockLLM(responses=[react_step_output, review_output])
        custom_agent = get_agent(llm=mock_llm)

        # Mock get_agent trong evaluate_event để dùng custom_agent
        with patch.object(evaluate_module, "get_agent", return_value=custom_agent):
            response = await evaluate_event(payload)

        self.assertIsInstance(response, AgentResponse)
        self.assertEqual(str(response.event_id), event_id)
        self.assertFalse(response.skip)
        self.assertIsNotNone(response.recommendation)
        self.assertEqual(response.recommendation.tool_name, "set_fan")
        self.assertEqual(response.recommendation.confidence, 0.85)
        self.assertIn("bật quạt", response.analysis)

    async def test_evaluate_event_safety_check_rejection(self):
        """Kiểm tra safety check: từ chối set_door khi phòng đang trong mode EXAM."""
        payload = make_sample_payload(room_mode="EXAM")
        event_id = payload["event_id"]
        room_id = payload["room_id"]

        # Agent cố gắng đề xuất set_door trong phòng thi
        react_step_output = (
            f'Self-Ask: Có nên mở cửa phòng?\n'
            f'Thought: Mở cửa phòng thi.\n'
            f'Action: finish\n'
            f'Action Input: {{"final_json": {{"event_id": "{event_id}", "recommendation": {{"tool_name": "set_door", "tool_params": {{"room_id": "{room_id}", "state": "unlocked"}}, "reason": "Yêu cầu mở cửa", "confidence": 0.85, "urgency": "medium"}}, "analysis": "Đề xuất mở cửa.", "skip": false}}}}'
        )
        review_output = json.dumps({"status": "Accomplished", "reasoning": "ok", "suggestions": None})

        mock_llm = MockLLM(responses=[react_step_output, review_output])
        custom_agent = get_agent(llm=mock_llm)

        with patch.object(evaluate_module, "get_agent", return_value=custom_agent):
            response = await evaluate_event(payload)

        # Safety check phải loại bỏ recommendation và đặt skip = True vì vi phạm mode EXAM
        self.assertTrue(response.skip)
        self.assertIsNone(response.recommendation)
        self.assertIn("final_safety_check_failed", response.skip_reason)

    async def test_evaluate_event_validation_error(self):
        """Kiểm tra xử lý lỗi 422 khi payload truyền vào thiếu các trường bắt buộc."""
        invalid_payload = {"some_random_key": 123}

        with self.assertRaises(HTTPException) as ctx:
            await evaluate_event(invalid_payload)

        self.assertEqual(ctx.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
