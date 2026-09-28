"""Isolation tests cho agent.

Bao gồm 3 lớp cô lập:
- Retrieval Isolation: kiểm tra retriever chọn đúng chunks.
- Tool Selection Isolation: kiểm tra LLM sinh đúng tool call JSON mà không thực thi.
- Prompt & Reasoning Isolation: kiểm tra suy luận với fake context/fake observation.
"""
from __future__ import annotations

import unittest

from app.evaluation.isolation import (
    compute_retrieval_metrics,
    validate_reasoning_step,
    validate_tool_selection,
)


class TestAgentIsolation(unittest.TestCase):
    def test_retrieval_isolation_metrics(self):
        """Retriever phải trả đúng chunk quan trọng và không lọt sai chunk."""
        relevant_docs = {
            "q1": ["temperature spike at room-a101"],
            "q2": ["schedule: no class at 19:45"],
        }
        retrieved = {
            "q1": ["temperature spike at room-a101", "general access log"],
            "q2": ["door log: manual override", "schedule: no class at 19:45"],
        }

        metrics = compute_retrieval_metrics(relevant_docs, retrieved, k=2)

        self.assertAlmostEqual(metrics["hit_rate"], 1.0)
        self.assertAlmostEqual(metrics["mrr"], 0.75)
        self.assertAlmostEqual(metrics["precision_at_k"], 0.5)

    def test_tool_selection_isolation_requires_valid_tool_and_arguments(self):
        """Agent phải sinh tool call đúng tên tool và tham số, nhưng chưa cần thực thi."""
        available = ["get_telemetry", "get_schedule", "send_alert"]

        raw_call = '{"tool": "get_telemetry", "arguments": {"room_id": "room-1", "metric": "temperature", "window": "1h"}}'
        result = validate_tool_selection(raw_call, available, required_arguments={"room_id": "room-1", "metric": "temperature"})

        self.assertTrue(result["valid"])
        self.assertEqual(result["tool_name"], "get_telemetry")
        self.assertEqual(result["arguments"]["window"], "1h")

        invalid_call = '{"tool": "unknown_tool", "arguments": {"room_id": "room-1"}}'
        invalid_result = validate_tool_selection(invalid_call, available)
        self.assertFalse(invalid_result["valid"])
        self.assertIn("unknown_tool", invalid_result["errors"][0] if invalid_result["errors"] else "")

    def test_prompt_reasoning_isolation_with_fake_context(self):
        """Fake context/fake observation phải dẫn đến suy luận/Thought đúng logic."""
        observation = {
            "room_id": "room-1",
            "mode": "LECTURE",
            "temperature": 32.5,
            "smoke_level": 0.02,
        }
        thought = (
            "Temperature is 32.5°C in LECTURE mode and rising above normal; "
            "the safe choice is to trigger set_fan."
        )

        result = validate_reasoning_step(
            observation,
            thought,
            required_facts=["32.5", "LECTURE", "set_fan"],
            expected_action="set_fan",
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["missing_facts"], [])


if __name__ == "__main__":
    unittest.main()
