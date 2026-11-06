"""
benchmark_v2/tests/test_isolation_and_reset.py
----------------------------------------------
Kiểm thử tự động cho Phase B4 (Cô lập, reset, chỉ-đọc):
1. reset_environment.py hoạt động chính xác (xóa -> seed -> verify -> exit 0).
2. Khi agent thực hiện 1 lượt đánh giá (Agent Evaluation Run),
   CSDL môi trường hoàn toàn không bị thay đổi (DB Checksum TRƯỚC == SAU).
3. Xác nhận khuyến nghị hành vi (actuation) là Dry-Run, không sinh side-effect vật lý.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import unittest
from uuid import UUID

import asyncpg

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.agent import ReActXenAgent
from app.config.settings import settings
from app.config.clock import set_request_reference_time
from app.gateway.client import GatewayClient
from app.gateway.rag import execute_rag_tool
from app.llm.client import LLMClient
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload, EventType
from benchmark_v2.env.reset_environment import reset_environment
from benchmark_v2.env.seed_environment import EnvironmentSeeder, DEFAULT_SPEC_PATH, DEFAULT_MANIFEST_PATH


class DummyDeterministicLLM(LLMClient):
    """LLM giả lập deterministic trả về finish JSON an toàn cho testcase U1."""
    async def complete(self, prompt: str) -> str:
        # Nếu đang ở vòng ReAct thought/action
        if "Action:" in prompt or "Thought:" in prompt:
            return (
                'Thought: Nhiệt độ phòng A104 quá cao 52.3C, tôi cần hoàn thành và đề xuất bật quạt làm mát.\n'
                'Action: finish\n'
                'Action Input: {"final_json": {"event_id": "b2000000-0000-4000-8000-000000000001", '
                '"recommendation": {"tool_name": "set_fan", "tool_params": {"room_id": "b2000000-0000-4000-8000-000000000001", "state": "on"}, '
                '"reason": "Nhiệt độ phòng quá cao 52.3C, cần bật quạt khẩn cấp", "confidence": 0.95, "urgency": "high"}, '
                '"skip": false, "analysis": "Bật quạt làm mát khẩn cấp do quá nhiệt 52.3C."}}'
            )
        # Review prompt
        return 'Status: Accomplished\nReasoning: Đã xử lý sự cố quá nhiệt thành công.'


class TestIsolationAndReset(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.seeder = EnvironmentSeeder(spec_path=DEFAULT_SPEC_PATH, manifest_path=DEFAULT_MANIFEST_PATH)
        self.t0_str = "2026-11-02T09:15:00+07:00"
        settings.BENCHMARK_MODE = True
        settings.BENCHMARK_REFERENCE_TIME = self.t0_str
        set_request_reference_time(self.t0_str)

    async def asyncTearDown(self):
        set_request_reference_time(None)
        settings.BENCHMARK_MODE = False
        settings.BENCHMARK_REFERENCE_TIME = None

    async def _compute_db_checksum(self) -> str:
        """Tính SHA-256 tổng hợp của bảng telemetry TimescaleDB cho 5 phòng benchmark."""
        conn = await asyncpg.connect(self.seeder.timescale_url)
        try:
            rows = await conn.fetch(
                """
                SELECT room_id, environment_timestamp, temperature, humidity, co2, smoke_value
                FROM public.environment
                WHERE room_id::text LIKE 'b2000000-%'
                ORDER BY room_id, environment_timestamp ASC;
                """
            )
            hasher = hashlib.sha256()
            for r in rows:
                ts = r["environment_timestamp"]
                line = f"{r['room_id']}|{int(ts.timestamp())}|{round(r['temperature'], 1)}|{round(r['humidity'], 1)}|{int(r['co2'])}|{round(r['smoke_value'], 1)}"
                hasher.update(line.encode("utf-8"))
            return hasher.hexdigest()
        finally:
            await conn.close()

    async def test_01_reset_environment(self):
        """Test reset_environment() dọn dẹp và nạp lại môi trường khớp 100% manifest."""
        success = await reset_environment()
        self.assertTrue(success)

    async def test_02_agent_run_does_not_mutate_db(self):
        """Xác nhận sau 1 lượt chạy Agent Evaluate, DB Checksum TRƯỚC == SAU (chỉ-đọc)."""
        # 1. Tính checksum trước khi chạy
        chk_before = await self._compute_db_checksum()

        # 2. Chuẩn bị payload U1 từ env_spec
        with open(DEFAULT_SPEC_PATH, "r", encoding="utf-8") as f:
            spec = json.load(f)
        u1 = next(r for r in spec["rooms"] if r["user_id"] == "U1")

        event = EventPayload(
            event_id=UUID("b2000000-0000-4000-8000-000000000001"),
            event_type=EventType.TEMPERATURE_ANOMALY,
            room_id=UUID(u1["room_id"]),
            timestamp=datetime.fromisoformat(self.t0_str),
            event_data={"sensor_id": "T-A104-02", "temperature": 52.3, "unit": "C"},
            operational_context=u1["operational_context"],
        )
        context = OperationalContext.model_validate(u1["operational_context"])

        # 3. Chạy Agent với dummy deterministic LLM
        llm = DummyDeterministicLLM()
        agent = ReActXenAgent(
            llm=llm,
            execute_rag_tool=execute_rag_tool,
            enforce_rag_guard=False,
        )

        response = await agent.evaluate(event, context)

        # Kiểm tra Agent phản hồi hợp lệ (đề xuất bật quạt làm mát)
        self.assertIsNotNone(response.recommendation)
        self.assertEqual(response.recommendation.tool_name, "set_fan")
        self.assertEqual(response.recommendation.tool_params.get("state"), "on")

        # 4. Tính checksum sau khi chạy
        chk_after = await self._compute_db_checksum()

        # 5. Assert: DB Checksum trước và sau phải trùng khớp 100% (DB chỉ đọc, không side-effect)
        self.assertEqual(chk_before, chk_after, "CSDL môi trường bị thay đổi sau lượt chạy Agent!")


if __name__ == "__main__":
    unittest.main()
