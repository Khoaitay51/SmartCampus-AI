"""
app/evaluation/evaluator.py
----------------------------
Engine chạy đánh giá hàng loạt kịch bản và xuất báo cáo kết quả.
"""
from __future__ import annotations

import time
import logging
from typing import Any

from app.agent.agent import ReActXenAgent
from app.evaluation.metrics import EvaluationMetrics
from app.evaluation.scenarios import BENCHMARK_SCENARIOS, TestScenario
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload

logger = logging.getLogger("app.evaluation.evaluator")


class AgentEvaluator:
    def __init__(self, agent: ReActXenAgent) -> None:
        self.agent = agent

    async def evaluate_scenario(self, scenario: TestScenario) -> dict[str, Any]:
        start_time = time.perf_counter()
        event = EventPayload.model_validate(scenario.event_payload)
        context = OperationalContext.model_validate(scenario.event_payload.get("operational_context", {}))

        response = await self.agent.evaluate(event, context)
        latency = time.perf_counter() - start_time

        recommended_tool = response.recommendation.tool if response.recommendation else None
        passed = (response.skip == scenario.should_skip) and (recommended_tool == scenario.expected_tool)

        return {
            "scenario": scenario.name,
            "passed": passed,
            "latency": latency,
            "confidence": response.confidence,
            "recommended_tool": recommended_tool,
            "expected_tool": scenario.expected_tool,
        }

    async def run_all(self) -> EvaluationMetrics:
        results = []
        for scenario in BENCHMARK_SCENARIOS:
            res = await self.evaluate_scenario(scenario)
            results.append(res)

        metrics = EvaluationMetrics()
        metrics.compute(results)
        logger.info("Hoàn tất đánh giá %d kịch bản: Accuracy=%.2f%%", metrics.total_scenarios, metrics.accuracy * 100)
        return metrics
