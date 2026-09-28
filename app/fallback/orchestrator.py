"""
fallback/orchestrator.py
------------------------
Bọc toàn bộ lần evaluate: chạy agent bình thường; nếu agent lỗi/quá thời gian/mọi LLM chết
thì rơi xuống rule-based (cấp 4). Luôn gắn cờ is_fallback vào kết quả để audit / LTM.

    result = await evaluate_with_fallback(event, run_agent=my_agent.run)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from .rules import evaluate_by_rules
from .trace import FallbackTrace, fallback_trace

logger = logging.getLogger("agent.fallback.orchestrator")


def _to_dict(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return dict(result)
    if hasattr(result, "model_dump"):  # pydantic (AgentResponse / RecommendationPayload)
        return result.model_dump()
    raise TypeError(f"Không chuyển được kết quả agent ({type(result).__name__}) sang dict")


def _annotate(result: dict[str, Any], trace: FallbackTrace) -> dict[str, Any]:
    result["is_fallback"] = trace.is_fallback
    result["fallback_levels"] = trace.levels
    if trace.is_fallback:
        seen = {(e.get("level"), e.get("detail")) for e in result.get("tool_calls_log") or [] if e.get("tool") == "fallback"}
        extra = [e for e in trace.to_log_entries() if (e["level"], e["detail"]) not in seen]
        result["tool_calls_log"] = list(result.get("tool_calls_log") or []) + extra
        analysis = result.get("analysis") or ""
        if not analysis.startswith("[FALLBACK"):
            result["analysis"] = f"[FALLBACK: {', '.join(trace.levels)}] {analysis}"
    return result


async def evaluate_with_fallback(
    event: dict[str, Any],
    run_agent: Callable[[dict[str, Any]], Awaitable[Any]],
    *,
    agent_timeout: float = 60.0,
) -> dict[str, Any]:
    with fallback_trace() as trace:
        try:
            result = _to_dict(await asyncio.wait_for(run_agent(event), timeout=agent_timeout))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - mọi lỗi agent đều phải có đường lui an toàn
            logger.error("Agent thất bại (%s: %s) -> rule-based fallback", type(exc).__name__, exc)
            result = evaluate_by_rules(event, reason=f"{type(exc).__name__}: {exc}")
        return _annotate(result, trace)
