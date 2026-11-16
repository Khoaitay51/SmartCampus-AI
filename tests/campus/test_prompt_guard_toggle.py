"""Unit tests cho SAFETY_PROMPT_GUARD_ENABLED (M1 Raw LLM vs M2 Prompt Guard)."""
import os
import unittest
from unittest import mock
import uuid

from app.agent.agent import ReActXenAgent
from app.agent.prompts import action_policy_for, build_react_prompt, find_action_policy_violations
from app.schemas.events import EventType
from app.schemas.recommendation import AgentResponse, ToolRecommendation

ENV = "SAFETY_PROMPT_GUARD_ENABLED"


class PromptGuardToggleTests(unittest.TestCase):
    def test_action_policy_restricts_when_enabled(self):
        with mock.patch.dict(os.environ, {ENV: "true"}):
            # TEMPERATURE_ANOMALY không cho phép set_door hay set_mode
            violations = find_action_policy_violations(EventType.TEMPERATURE_ANOMALY, "set_door")
            self.assertEqual(len(violations), 1)

    def test_action_policy_allows_all_tools_when_disabled(self):
        with mock.patch.dict(os.environ, {ENV: "false"}):
            policy = action_policy_for(EventType.TEMPERATURE_ANOMALY)
            self.assertIn("set_door", policy.candidate_tools)
            self.assertIn("set_mode", policy.candidate_tools)
            self.assertEqual(
                find_action_policy_violations(EventType.TEMPERATURE_ANOMALY, "set_door"),
                [],
            )

    def test_final_safety_check_respects_prompt_guard_flag(self):
        agent = ReActXenAgent.__new__(ReActXenAgent)
        ev_id = uuid.uuid4()

        def make_low_conf_resp() -> AgentResponse:
            return AgentResponse(
                event_id=ev_id,
                recommendation=ToolRecommendation(
                    tool_name="set_door",
                    tool_params={"state": "unlocked"},
                    reason="test",
                    confidence=0.20,
                    urgency="high",
                ),
                analysis="test low confidence",
                skip=False,
            )

        with mock.patch.dict(os.environ, {ENV: "true"}):
            checked = agent._final_safety_check(make_low_conf_resp(), None)  # type: ignore[arg-type]
            self.assertTrue(checked.skip)
            self.assertIsNone(checked.recommendation)

        with mock.patch.dict(os.environ, {ENV: "false"}):
            checked = agent._final_safety_check(make_low_conf_resp(), None)  # type: ignore[arg-type]
            self.assertFalse(checked.skip)
            self.assertIsNotNone(checked.recommendation)
            self.assertEqual(checked.recommendation.tool_name, "set_door")

    def test_build_react_prompt_strips_guard_blocks_when_disabled(self):
        with mock.patch.dict(os.environ, {ENV: "true"}):
            guarded = build_react_prompt(
                event_type=EventType.TEMPERATURE_ANOMALY,
                tool_desc="- `set_fan`: fan",
                tool_names="get_telemetry, set_fan, finish",
                max_rag_calls=5,
                reflections="",
                event_context="{}",
                scratchpad="",
            )
        self.assertIn("First-Touch Mandatory", guarded)
        self.assertIn("Tiny Trajectory Store", guarded)

        with mock.patch.dict(os.environ, {ENV: "false"}):
            unguarded = build_react_prompt(
                event_type=EventType.TEMPERATURE_ANOMALY,
                tool_desc="- `set_fan`: fan",
                tool_names="get_telemetry, set_fan, finish",
                max_rag_calls=5,
                reflections="",
                event_context="{}",
                scratchpad="",
            )
        self.assertNotIn("First-Touch Mandatory", unguarded)
        self.assertNotIn("Tiny Trajectory Store", unguarded)

    def test_final_safety_check_enforces_action_policy_at_runtime(self):
        agent = ReActXenAgent.__new__(ReActXenAgent)
        resp = AgentResponse(
            event_id=uuid.uuid4(),
            recommendation=ToolRecommendation(
                tool_name="set_door",
                tool_params={"state": "unlocked"},
                reason="test high conf policy violation",
                confidence=0.90,
                urgency="high",
            ),
            analysis="test",
            skip=False,
        )
        with mock.patch.dict(os.environ, {ENV: "true"}):
            checked = agent._final_safety_check(resp, None, event_type=EventType.TEMPERATURE_ANOMALY)
            self.assertTrue(checked.skip)
            self.assertIn("final_safety_check_failed:", checked.skip_reason or "")


if __name__ == "__main__":
    unittest.main()

