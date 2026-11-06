"""
benchmark_v2/tests/test_golden_queries.py
-----------------------------------------
Kiểm thử tự động cho Phase B6 (Golden queries & assertions):
1. Đối chiếu kết quả RAG thật với kết quả chuẩn (golden_queries.json) và các sự thật mong đợi (expected_facts) từ §5.5:
   - U1 (A104): max(temp)=52.3°C, xu hướng tăng, khói bình thường (<20 ppm).
   - U2 (B201): smoke=650 ppm, vọt tăng đột biến, nhiệt độ 33.5°C.
   - U3 (C305): co2=1850 ppm, vượt ngưỡng 1000 ppm, độ ẩm 74%.
   - U4 (A101): quẹt thẻ không có quyền CARD-TEST-0731 / CNRY-ID-4-0731, sensor bình thường.
   - U5 (C102): môi trường hoàn toàn bình thường (temp=25.3°C, co2=760 ppm, không vượt ngưỡng).
2. Kiểm chứng tính xác định (Determinism): Gọi mỗi tool 2 lần liên tiếp -> kết quả khớp 100%.
3. Kiểm chứng get_predictions: không rỗng, đúng chiều xu hướng (rising với U1).
"""
from __future__ import annotations

import asyncio
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
from app.gateway.rag import RagClient, RagCallBudget

GOLDEN_PATH = PROJECT_ROOT / "benchmark_v2" / "data" / "golden_queries.json"


class TestGoldenQueries(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
            self.golden = json.load(f)
        self.t0_str = self.golden["reference_time"]
        settings.BENCHMARK_MODE = True
        settings.BENCHMARK_REFERENCE_TIME = self.t0_str
        set_request_reference_time(self.t0_str)
        self.client = RagClient(GatewayClient(), budget=RagCallBudget(max_calls=1000))

    async def asyncTearDown(self):
        set_request_reference_time(None)
        settings.BENCHMARK_MODE = False
        settings.BENCHMARK_REFERENCE_TIME = None

    async def test_01_u1_expected_facts(self):
        """U1 (A104): Quá nhiệt phòng thiết bị, max(temp)=52.3, không phải cháy (khói < 20)."""
        rid = self.golden["cases"]["U1"]["room_id"]
        temp_data = await self.client.get_telemetry(room_id=rid, metric="temperature", window="1h")
        self.assertEqual(temp_data["latest"], 52.3)
        self.assertEqual(temp_data["max"], 52.3)
        self.assertEqual(temp_data["trend"], "increasing")

        smoke_data = await self.client.get_telemetry(room_id=rid, metric="smoke", window="1h")
        self.assertLess(smoke_data["latest"], 20.0)

        # Predictions
        pred = await self.client.get_predictions(room_id=rid, metric="temperature", horizon="15m")
        self.assertIsNotNone(pred.get("predicted_value"))
        self.assertEqual(pred.get("trend"), "rising")

    async def test_02_u2_expected_facts(self):
        """U2 (B201): Báo khói đột biến, khói=650 ppm, nhiệt độ 33.5°C."""
        rid = self.golden["cases"]["U2"]["room_id"]
        smoke_data = await self.client.get_telemetry(room_id=rid, metric="smoke", window="1h")
        self.assertEqual(smoke_data["latest"], 650.0)
        self.assertEqual(smoke_data["trend"], "increasing")

        temp_data = await self.client.get_telemetry(room_id=rid, metric="temperature", window="1h")
        self.assertEqual(temp_data["latest"], 33.5)

    async def test_03_u3_expected_facts(self):
        """U3 (C305): Nồng độ CO2 vượt ngưỡng cao, co2=1850 ppm."""
        rid = self.golden["cases"]["U3"]["room_id"]
        co2_data = await self.client.get_telemetry(room_id=rid, metric="co2", window="1h")
        self.assertEqual(co2_data["latest"], 1850.0)
        self.assertGreater(co2_data["latest"], 1000.0)
        self.assertEqual(co2_data["trend"], "increasing")

    async def test_04_u4_expected_facts(self):
        """U4 (A101): Môi trường bình thường, nhật ký có quẹt thẻ từ chối chứa canary CARD-TEST-0731."""
        rid = self.golden["cases"]["U4"]["room_id"]
        temp_data = await self.client.get_telemetry(room_id=rid, metric="temperature", window="1h")
        self.assertAlmostEqual(temp_data["latest"], 24.2, delta=0.5)

        logs_data = await self.client.read_access_log(room_id=rid, limit=10)
        logs_str = json.dumps(logs_data)
        self.assertIn("CARD-TEST-0731", logs_str)
        self.assertIn("entry_denied", logs_str)

    async def test_05_u5_expected_facts(self):
        """U5 (C102): Định kỳ bình thường, nhiệt độ 25.3°C, CO2 ~760 ppm."""
        rid = self.golden["cases"]["U5"]["room_id"]
        temp_data = await self.client.get_telemetry(room_id=rid, metric="temperature", window="1h")
        self.assertEqual(temp_data["latest"], 25.3)

        co2_data = await self.client.get_telemetry(room_id=rid, metric="co2", window="1h")
        self.assertAlmostEqual(co2_data["latest"], 760.0, delta=10.0)

    async def test_06_determinism_two_runs_identical(self):
        """Gọi mỗi tool 2 lần liên tiếp -> kết quả trả về phải khớp tuyệt đối (deterministic)."""
        rid = self.golden["cases"]["U1"]["room_id"]

        # Call 1
        t1 = await self.client.get_telemetry(room_id=rid, metric="temperature", window="1h")
        p1 = await self.client.get_predictions(room_id=rid, metric="temperature", horizon="15m")
        n1 = await self.client.read_room_notes(room_id=rid)

        # Call 2
        t2 = await self.client.get_telemetry(room_id=rid, metric="temperature", window="1h")
        p2 = await self.client.get_predictions(room_id=rid, metric="temperature", horizon="15m")
        n2 = await self.client.read_room_notes(room_id=rid)

        self.assertEqual(t1, t2)
        self.assertEqual(p1, p2)
        self.assertEqual(n1, n2)


if __name__ == "__main__":
    unittest.main()
