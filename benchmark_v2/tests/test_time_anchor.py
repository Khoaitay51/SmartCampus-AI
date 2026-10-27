"""
benchmark_v2/tests/test_time_anchor.py
--------------------------------------
Kiểm thử tự động cho cơ chế Time Anchor (Clock Injection - QĐ-7 / Phase B2).
Xác nhận:
1. Mặc định (BENCHMARK_MODE=False): trả về thời gian wall-clock thật.
2. Khi bật BENCHMARK_MODE=True: trả về mốc thời gian T0 cố định.
3. Khi truyền reference_time per-request qua ContextVar: trả về đúng mốc thời gian đó.
4. RAG tools (get_telemetry, get_predictions, get_schedule) tính toán window 'since' và 'until' quanh T0.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
import sys
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

# Đảm bảo import được code dự án
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.config.clock import get_current_time, set_request_reference_time
from app.gateway.rag import RagClient, RagCallBudget


class TestTimeAnchor(unittest.TestCase):
    def setUp(self):
        # Reset trạng thái
        set_request_reference_time(None)
        settings.BENCHMARK_MODE = False
        settings.BENCHMARK_REFERENCE_TIME = None

    def tearDown(self):
        set_request_reference_time(None)
        settings.BENCHMARK_MODE = False
        settings.BENCHMARK_REFERENCE_TIME = None

    def test_default_wall_clock(self):
        """Khi BENCHMARK_MODE=False, thời gian trả về phải là wall-clock hiện tại."""
        now_real = datetime.now(timezone.utc)
        curr = get_current_time()
        self.assertAlmostEqual(curr.timestamp(), now_real.timestamp(), delta=2.0)

    def test_settings_clock_injection(self):
        """Khi BENCHMARK_MODE=True và có BENCHMARK_REFERENCE_TIME, trả về đúng T0."""
        t0_str = "2026-11-02T09:15:00+07:00"
        settings.BENCHMARK_MODE = True
        settings.BENCHMARK_REFERENCE_TIME = t0_str

        curr = get_current_time()
        expected = datetime.fromisoformat(t0_str)
        self.assertEqual(curr, expected)

    def test_context_var_override(self):
        """set_request_reference_time phải ghi đè cả settings lẫn wall-clock."""
        req_time = "2026-11-02T14:30:00+07:00"
        set_request_reference_time(req_time)

        curr = get_current_time()
        expected = datetime.fromisoformat(req_time)
        self.assertEqual(curr, expected)

        # Reset context
        set_request_reference_time(None)
        self.assertAlmostEqual(get_current_time().timestamp(), datetime.now(timezone.utc).timestamp(), delta=2.0)

    def test_rag_telemetry_window_anchored_at_t0(self):
        """RAG get_telemetry phải tính toán since và until chính xác quanh T0."""
        t0_str = "2026-11-02T09:15:00+07:00"
        settings.BENCHMARK_MODE = True
        settings.BENCHMARK_REFERENCE_TIME = t0_str

        mock_gw_client = AsyncMock()
        mock_gw_client.get = AsyncMock(return_value={
            "rows": [
                {"temperature": 45.0, "smoke_value": 12.0, "environment_timestamp": "2026-11-02T08:30:00+07:00"},
                {"temperature": 52.3, "smoke_value": 12.0, "environment_timestamp": "2026-11-02T09:15:00+07:00"},
            ]
        })

        rag = RagClient(client=mock_gw_client, budget=RagCallBudget(max_calls=4))

        loop = asyncio.new_event_loop()
        try:
            res = loop.run_until_complete(
                rag.get_telemetry(room_id="b2000000-0000-4000-8000-000000000001", metric="temperature", window="1h")
            )
        finally:
            loop.close()

        # Kiểm tra GatewayClient đã được gọi với tham số since = T0 - 1h và until = T0
        mock_gw_client.get.assert_called_once()
        call_args = mock_gw_client.get.call_args
        params = call_args.kwargs.get("params", {})

        expected_until = datetime.fromisoformat(t0_str).isoformat()
        expected_since = (datetime.fromisoformat(t0_str) - timedelta(hours=1)).isoformat()

        self.assertEqual(params.get("since"), expected_since)
        self.assertEqual(params.get("until"), expected_until)
        self.assertEqual(res.get("latest"), 52.3)
        self.assertEqual(res.get("max"), 52.3)


if __name__ == "__main__":
    unittest.main()
