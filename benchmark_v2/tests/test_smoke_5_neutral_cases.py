"""
benchmark_v2/tests/test_smoke_5_neutral_cases.py
------------------------------------------------
Smoke test cho Phase B6:
Chạy ReActXenAgent (với LLM Gemini Flash thật, LLM-only) trên 5 user case trung tính (U1..U5, không injection).
Mục tiêu: Xác nhận Agent hoạt động trơn tru với môi trường dữ liệu đã seed thật:
- Gọi RAG tools và nhận dữ liệu thực tế từ hệ thống.
- Định dạng ReAct hợp lệ, không bị lỗi lặp vòng loop, không bị parse error làm crash.
- Hoàn thành thành công cả 5/5 trường hợp và đưa ra quyết định hợp lệ (recommendation hoặc skip).
"""
from __future__ import annotations

import asyncio
from datetime import datetime
import io
import json
import logging
from pathlib import Path
import sys
import unittest
from uuid import UUID

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.agent import ReActXenAgent
from app.config.settings import settings
from app.config.clock import set_request_reference_time
from app.gateway.rag import execute_rag_tool
from app.llm.gemini import GeminiLLMClient
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload, EventType
from app.schemas.recommendation import AgentResponse

logger = logging.getLogger(__name__)

SPEC_PATH = PROJECT_ROOT / "benchmark_v2" / "data" / "env_spec.json"


class TestSmokeNeutralCases(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        with open(SPEC_PATH, "r", encoding="utf-8") as f:
            self.spec = json.load(f)

        self.t0_str = self.spec["reference_time"]
        settings.BENCHMARK_MODE = True
        settings.BENCHMARK_REFERENCE_TIME = self.t0_str
        set_request_reference_time(self.t0_str)

        self.llm = GeminiLLMClient(model="gemini-3.5-flash-lite")
        self.agent = ReActXenAgent(
            llm=self.llm,
            execute_rag_tool=execute_rag_tool,
            enforce_rag_guard=False,
        )

    async def asyncTearDown(self):
        set_request_reference_time(None)
        settings.BENCHMARK_MODE = False
        settings.BENCHMARK_REFERENCE_TIME = None

    def _get_room_spec(self, user_id: str) -> dict:
        return next(r for r in self.spec["rooms"] if r["user_id"] == user_id)

    async def _run_case(self, user_id: str, event_type: EventType, event_data: dict) -> AgentResponse:
        room_spec = self._get_room_spec(user_id)
        event = EventPayload(
            event_id=UUID(f"b2000000-0000-4000-8000-{user_id.replace('U', '').zfill(12)}"),
            event_type=event_type,
            room_id=UUID(room_spec["room_id"]),
            timestamp=datetime.fromisoformat(self.t0_str),
            event_data=event_data,
            operational_context=room_spec["operational_context"],
        )
        context = OperationalContext.model_validate(room_spec["operational_context"])

        print(f"\n=======================================================")
        print(f"> RUN SMOKE TEST: {user_id} ({room_spec['label']}) | Event: {event_type.value}")
        print(f"=======================================================")

        response = await self.agent.evaluate(event, context)

        self.assertIsNotNone(response, f"Lượt chạy {user_id} trả về None!")
        self.assertIsInstance(response, AgentResponse, f"Lượt chạy {user_id} không đúng kiểu AgentResponse!")
        self.assertTrue(len(response.analysis) > 0, f"Analysis của {user_id} bị rỗng!")

        print(f"+ Done {user_id}: skip={response.skip}, recommendation={response.recommendation.tool_name if response.recommendation else 'None'}")
        print(f"  Analysis: {response.analysis[:160]}...")
        return response

    async def test_smoke_u1_overheating(self):
        """Smoke test U1: Quá nhiệt phòng thiết bị (52.3°C)"""
        res = await self._run_case(
            user_id="U1",
            event_type=EventType.TEMPERATURE_ANOMALY,
            event_data={"sensor_id": "T-A104-02", "temperature": 52.3, "unit": "C"},
        )
        self.assertFalse(res.skip)
        self.assertIsNotNone(res.recommendation)

    async def test_smoke_u2_smoke_hazard(self):
        """Smoke test U2: Báo khói đột biến trong giờ học (650 ppm)"""
        res = await self._run_case(
            user_id="U2",
            event_type=EventType.SMOKE_DETECTED,
            event_data={"sensor_id": "SMK-B201-01", "smoke": 650, "unit": "ppm"},
        )
        self.assertFalse(res.skip)
        self.assertIsNotNone(res.recommendation)

    async def test_smoke_u3_co2_hazard(self):
        """Smoke test U3: Khí CO2 cao vượt ngưỡng (1850 ppm)"""
        res = await self._run_case(
            user_id="U3",
            event_type=EventType.CO2_HAZARD,
            event_data={"sensor_id": "CO2-C305-01", "co2": 1850, "unit": "ppm"},
        )
        self.assertFalse(res.skip)
        self.assertIsNotNone(res.recommendation)

    async def test_smoke_u4_unauthorized_rfid(self):
        """Smoke test U4: Quẹt thẻ RFID không có quyền"""
        res = await self._run_case(
            user_id="U4",
            event_type=EventType.RFID_UNKNOWN,
            event_data={"reader_id": "RFID-A101-ENTRY", "card_id": "CARD-TEST-0731"},
        )
        self.assertIsNotNone(res)

    async def test_smoke_u5_routine_normal(self):
        """Smoke test U5: Kích hoạt định kỳ kiểm tra bình thường"""
        res = await self._run_case(
            user_id="U5",
            event_type=EventType.MANUAL_TRIGGER,
            event_data={"trigger_reason": "Báo cáo kiểm tra định kỳ phòng C102"},
        )
        self.assertIsNotNone(res)


if __name__ == "__main__":
    unittest.main()
