"""
app/evaluation/scenarios.py
----------------------------
Định nghĩa tập kịch bản thử nghiệm (Test Scenarios) cho Agent.
"""
from dataclasses import dataclass
from typing import Any


@dataclass
class TestScenario:
    name: str
    event_payload: dict[str, Any]
    expected_tool: str | None
    should_skip: bool = False


BENCHMARK_SCENARIOS: list[TestScenario] = [
    TestScenario(
        name="Quá nhiệt trong phòng học",
        event_payload={
            "event_id": "evt-eval-001",
            "event_type": "temperature_anomaly",
            "room_id": "ROOM-101",
            "timestamp": "2026-09-23T10:00:00Z",
            "metrics": {"temperature": 34.5, "humidity": 70.0},
            "operational_context": {"room_mode": "LECTURE", "occupancy": 30},
        },
        expected_tool="set_fan",
        should_skip=False,
    ),
    TestScenario(
        name="Báo khói khẩn cấp",
        event_payload={
            "event_id": "evt-eval-002",
            "event_type": "smoke_detected",
            "room_id": "ROOM-102",
            "timestamp": "2026-09-23T10:05:00Z",
            "metrics": {"smoke": 0.85},
            "operational_context": {"room_mode": "EMERGENCY", "occupancy": 15},
        },
        expected_tool="trigger_buzzer",
        should_skip=False,
    ),
]
