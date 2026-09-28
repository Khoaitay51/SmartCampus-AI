"""
tests/fallback/test_agent_fallback_integration.py
---------------------------------------------------
Integration tests cho 3 kịch bản fallback chính của AI Agent:
  1. LLM fail -> fallback model
  2. model fail + JSON parse fail -> regex scrape (parsing fallback)
  3. toàn bộ fail -> rule-based fallback
"""
from __future__ import annotations

import asyncio
import json
import unittest
from uuid import uuid4

from app.agent.agent import ReActXenAgent
from app.fallback import CircuitBreaker, FallbackLLMClient, ProviderSpec
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload, EventType


class ScriptedLLM:
    def __init__(self, *outputs: str | Exception):
        self.outputs = list(outputs)
        self.calls = 0

    async def complete(self, prompt: str) -> str:
        self.calls += 1
        out = self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
        if isinstance(out, Exception):
            raise out
        return out


def make_test_event_and_context(event_type: EventType = EventType.TEMPERATURE_ANOMALY, temp: float = 36.2) -> tuple[EventPayload, OperationalContext]:
    event_id = str(uuid4())
    room_id = str(uuid4())
    context = OperationalContext.model_validate({
        "room": {
            "room_id": room_id,
            "room_name": "Phòng A101",
            "room_type": "lecture_hall",
            "current_mode": "LECTURE",
            "smoke_state": "normal",
        },
        "telemetry_summary": {
            "window_start": "2026-09-22T08:00:00+07:00",
            "window_end": "2026-09-22T08:30:00+07:00",
            "temperature": {"min": 28.5, "max": temp, "avg": 33.1, "latest": temp},
            "humidity": {"min": 60.0, "max": 75.0, "avg": 68.0, "latest": 71.0},
            "co2": {"min": 800.0, "max": 1450.0, "avg": 1100.0, "latest": 1450.0},
            "smoke_value": {"min": 0.0, "max": 2.0, "avg": 0.5, "latest": 0.0},
            "air_quality": {"min": 55.0, "max": 80.0, "avg": 65.0, "latest": 58.0},
        },
        "occupancy": {"current_count": 30, "total_in": 30, "total_out": 0, "trend": "stable"},
        "active_session": None,
        "recent_events": [],
    })
    event = EventPayload.model_validate({
        "event_id": event_id,
        "event_type": event_type.value,
        "room_id": room_id,
        "timestamp": "2026-09-22T08:30:00+07:00",
        "event_data": {"temperature": temp},
        "operational_context": context.model_dump(mode="json"),
    })
    return event, context


class AgentFallbackIntegrationTests(unittest.IsolatedAsyncioTestCase):

    async def test_scenario_1_llm_fail_to_fallback_model(self):
        """Kịch bản 1: Primary LLM fail -> tự động chuyển sang Fallback Model."""
        primary = ScriptedLLM(RuntimeError("503 Service Unavailable"))
        valid_finish_output = (
            "Thought: Primary model failed, secondary model is concluding recommendation\n"
            "Action: finish\n"
            'Action Input: {"final_json": {"tool_name": "set_fan", "tool_params": {"state": "on"}, '
            '"reason": "Nhiệt độ phòng quá cao 36.2°C trong giờ học", "confidence": 0.9, "urgency": "high"}}'
        )
        secondary = ScriptedLLM(valid_finish_output)

        fallback_llm = FallbackLLMClient([
            ProviderSpec("primary", primary, CircuitBreaker("p", failure_threshold=2)),
            ProviderSpec("secondary", secondary, CircuitBreaker("s")),
        ])

        agent = ReActXenAgent(llm=fallback_llm)
        event, context = make_test_event_and_context()

        response = await agent.evaluate(event, context)

        self.assertTrue(response.is_fallback)
        self.assertIn("model", response.fallback_levels)
        self.assertIsNotNone(response.recommendation)
        self.assertEqual(response.recommendation.tool_name, "set_fan")
        self.assertIn("[FALLBACK:", response.analysis)

    async def test_scenario_2_model_fail_and_json_parse_fail_to_regex_scrape(self):
        """Kịch bản 2: Model fail + JSON parse fail -> Cạo dữ liệu bằng Regex (parsing fallback)."""
        primary = ScriptedLLM(RuntimeError("503 Service Unavailable"))
        unstructured_output = (
            "Thought: Secondary model output has invalid final_json format\n"
            "Action: finish\n"
            'Action Input: {"tool_name": "set_fan", "confidence": 0.95, "urgency": "high", "reason": "Nhiệt độ quá nóng 36.2C"}'
        )
        secondary = ScriptedLLM(unstructured_output)

        fallback_llm = FallbackLLMClient([
            ProviderSpec("primary", primary, CircuitBreaker("p")),
            ProviderSpec("secondary", secondary, CircuitBreaker("s")),
        ])

        agent = ReActXenAgent(llm=fallback_llm)
        event, context = make_test_event_and_context()

        response = await agent.evaluate(event, context)

        self.assertTrue(response.is_fallback)
        self.assertIn("model", response.fallback_levels)
        self.assertIn("parsing", response.fallback_levels)
        self.assertIsNotNone(response.recommendation)
        self.assertEqual(response.recommendation.tool_name, "set_fan")
        # Regex scraped confidence phải bị chốt cap <= 0.6
        self.assertLessEqual(response.recommendation.confidence, 0.6)

    async def test_scenario_3_all_fail_to_rule_based_fallback(self):
        """Kịch bản 3: Toàn bộ LLM provider fail -> chuyển sang Rule-Based Fallback."""
        primary = ScriptedLLM(RuntimeError("503 Primary Dead"))
        secondary = ScriptedLLM(RuntimeError("503 Secondary Dead"))

        fallback_llm = FallbackLLMClient([
            ProviderSpec("primary", primary, CircuitBreaker("p")),
            ProviderSpec("secondary", secondary, CircuitBreaker("s")),
        ])

        agent = ReActXenAgent(llm=fallback_llm)
        event, context = make_test_event_and_context(temp=36.2)

        response = await agent.evaluate(event, context)

        self.assertTrue(response.is_fallback)
        self.assertIn("rules", response.fallback_levels)
        self.assertIsNotNone(response.recommendation)
        self.assertEqual(response.recommendation.tool_name, "set_fan")
        self.assertIn("[FALLBACK: rules]", response.analysis)

    async def test_smoke_emergency_rule_fallback(self):
        """Rule fallback cho sự kiện báo khói."""
        primary = ScriptedLLM(RuntimeError("503 Primary Dead"))
        secondary = ScriptedLLM(RuntimeError("503 Secondary Dead"))

        fallback_llm = FallbackLLMClient([
            ProviderSpec("primary", primary, CircuitBreaker("p")),
            ProviderSpec("secondary", secondary, CircuitBreaker("s")),
        ])

        agent = ReActXenAgent(llm=fallback_llm)
        event_id = str(uuid4())
        room_id = str(uuid4())
        context = OperationalContext.model_validate({
            "room": {
                "room_id": room_id,
                "room_name": "Lab B202",
                "room_type": "lab",
                "current_mode": "EMERGENCY",
                "smoke_state": "suspected",
            },
            "telemetry_summary": {
                "window_start": "2026-09-22T09:30:00+07:00",
                "window_end": "2026-09-22T09:45:00+07:00",
                "temperature": {"min": 27.0, "max": 40.5, "avg": 31.2, "latest": 40.5},
                "humidity": {"min": 45.0, "max": 65.0, "avg": 55.0, "latest": 58.0},
                "co2": {"min": 400.0, "max": 1800.0, "avg": 900.0, "latest": 1750.0},
                "smoke_value": {"min": 50.0, "max": 620.0, "avg": 310.0, "latest": 620.0},
                "air_quality": {"min": 20.0, "max": 60.0, "avg": 38.0, "latest": 22.0},
            },
            "occupancy": {"current_count": 6, "total_in": 8, "total_out": 2, "trend": "leaving"},
            "active_session": None,
            "recent_events": [],
        })
        event = EventPayload.model_validate({
            "event_id": event_id,
            "event_type": EventType.SMOKE_DETECTED.value,
            "room_id": room_id,
            "timestamp": "2026-09-22T09:45:00+07:00",
            "event_data": {"smoke_value": 620.0, "smoke_state": "suspected"},
            "operational_context": context.model_dump(mode="json"),
        })

        response = await agent.evaluate(event, context)

        self.assertTrue(response.is_fallback)
        self.assertIn("rules", response.fallback_levels)
        self.assertIsNotNone(response.recommendation)
        self.assertEqual(response.recommendation.tool_name, "trigger_buzzer")
        self.assertEqual(response.recommendation.urgency, "high")


if __name__ == "__main__":
    unittest.main()
