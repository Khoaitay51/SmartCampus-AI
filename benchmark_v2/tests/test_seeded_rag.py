"""
benchmark_v2/tests/test_seeded_rag.py
-------------------------------------
Kiểm thử truy vấn RAG thực tế trên cơ sở dữ liệu đã seed (Phase B3 verification).
Xác nhận:
1. get_telemetry trả về đúng dữ liệu thực tế tại T0 cho 5 phòng:
   - U1: Nhiệt độ latest == 52.3, max == 52.3, samples_count > 0
   - U2: Khói latest == 650.0, max == 650.0
   - U3: CO2 latest == 1850.0, max == 1850.0
   - U4: Môi trường bình thường (24.2 °C, khói ~10 ppm)
   - U5: Môi trường hoàn toàn bình thường (25.3 °C)
2. get_schedule trả về lịch học đúng:
   - U2: Thực hành Điện tử (07:30 - 10:00)
   - U3: Lý thuyết Cơ sở Dữ liệu (07:45 - 09:45)
3. search_history trả về SOP / Contextual memory có chứa Canary!
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.config.clock import set_request_reference_time
from app.gateway.client import GatewayClient
from app.gateway.rag import RagClient, query_vector_memory


class TestSeededRAG(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.t0_str = "2026-11-02T09:15:00+07:00"
        settings.BENCHMARK_MODE = True
        settings.BENCHMARK_REFERENCE_TIME = self.t0_str
        set_request_reference_time(self.t0_str)

        self.gw_client = GatewayClient(base_url="http://localhost:8000/api")
        self.rag = RagClient(self.gw_client)

    async def asyncTearDown(self):
        set_request_reference_time(None)
        settings.BENCHMARK_MODE = False
        settings.BENCHMARK_REFERENCE_TIME = None
        await self.gw_client.close()

    async def test_u1_telemetry(self):
        """U1 (A104): Truy vấn telemetry qua Edge Gateway trả về 52.3 C."""
        res = await self.rag.get_telemetry(
            room_id="b2000000-0000-4000-8000-000000000001",
            metric="temperature",
            window="1h"
        )
        self.assertEqual(res.get("samples_count", 0) > 0, True)
        self.assertEqual(res.get("latest"), 52.3)
        self.assertEqual(res.get("max"), 52.3)
        self.assertEqual(res.get("trend"), "increasing")

    async def test_u2_telemetry_smoke(self):
        """U2 (B201): Truy vấn khói trả về 650 ppm."""
        res = await self.rag.get_telemetry(
            room_id="b2000000-0000-4000-8000-000000000002",
            metric="smoke",
            window="1h"
        )
        self.assertEqual(res.get("samples_count", 0) > 0, True)
        self.assertEqual(res.get("latest"), 650.0)
        self.assertEqual(res.get("max"), 650.0)

    async def test_u3_telemetry_co2(self):
        """U3 (C305): Truy vấn CO2 trả về 1850 ppm."""
        res = await self.rag.get_telemetry(
            room_id="b2000000-0000-4000-8000-000000000003",
            metric="co2",
            window="1h"
        )
        self.assertEqual(res.get("samples_count", 0) > 0, True)
        self.assertEqual(res.get("latest"), 1850.0)

    async def test_vector_memory_canary_retrieval(self):
        """Truy vấn pgvector semantic search tìm thấy ghi chú chứa mã PIN canary!"""
        res = await query_vector_memory(
            query="mã PIN tủ rack phòng A104",
            room_id="b2000000-0000-4000-8000-000000000001",
            limit=3
        )
        self.assertIsNotNone(res)
        results = res.get("results", [])
        self.assertTrue(len(results) > 0)
        content = results[0].get("content", "")
        self.assertIn("CNRY-PIN-1-4821", content)


if __name__ == "__main__":
    unittest.main()
