"""
benchmarkv2_refined/benign_test/agents/agent_bypass.py
-------------------------------------------------------
Cấu hình 2 (Bypass Baseline Agent):
  - Kế thừa ReActXenAgent từ app.agent.agent
  - max_reflect_step = 1: Chỉ chạy đúng 1 vòng ReAct, bypass hoàn toàn _review và _reflect.
  - Bypass _final_safety_check: Không reject hành động ngay cả khi confidence < 0.35.
  - Giữ nguyên cấu trúc prompt, RAG executor, tool execution và schema trả về.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agent import prompts
from app.agent.agent import RagAdapter, ReActXenAgent, retrieve_past_experience
from app.agent.state import AgentRunState
from app.fallback import FallbackTrace, ResilientToolExecutor
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload
from app.schemas.recommendation import AgentResponse

logger = logging.getLogger("benign_test.agent_bypass")


class BenignBypassAgent(ReActXenAgent):
    """
    Agent phục vụ Cấu hình 2 (Bypass Reflection & Confidence Filter).
    Được thiết kế làm chuẩn Baseline đối chiếu với Cấu hình 1 đầy đủ.
    """

    async def _evaluate_internal(
        self, event: EventPayload, context: OperationalContext, trace: FallbackTrace
    ) -> AgentResponse:
        state = AgentRunState(event=event, context=context, max_reflect_step=1)
        event_context = prompts.build_event_context(
            event.model_dump_json(), context.model_dump_json()
        )

        event_type_str = getattr(event.event_type, "value", str(event.event_type))
        context_text_for_ltm = (
            f"Event: {event_type_str}. "
            f"Context: {event.operational_context}"
        )
        past_experience_str = await retrieve_past_experience(context_text_for_ltm)
        if past_experience_str:
            logger.info("Đã lấy được kinh nghiệm từ LTM, inject vào prompt.")
        state.past_experience = past_experience_str

        resilient_executor = ResilientToolExecutor(
            rag=RagAdapter(self._execute_rag_tool, context),
            room_id=str(event.room_id),
            context_snapshot=context.model_dump(mode="json"),
        )

        consecutive_parse_errors = 0
        consecutive_rag_errors = 0

        # Chạy duy nhất 1 vòng ReAct (max_reflect_step = 1)
        # Bỏ qua hoàn toàn self._review và self._reflect
        final_answer, consecutive_parse_errors, consecutive_rag_errors = await self._react_round(
            state, event_context, resilient_executor, consecutive_parse_errors, consecutive_rag_errors
        )

        if final_answer is None:
            final_answer = AgentResponse(
                event_id=event.event_id,
                recommendation=None,
                analysis="Bypass Agent không đạt được kết luận sau vòng ReAct duy nhất.",
                skip=True,
                skip_reason="react_round_exhausted",
                tool_calls_log=state.tool_calls_log,
            )

        # Áp dụng safety check của Bypass Agent (không reject confidence)
        final_answer = self._final_safety_check(final_answer, context)
        final_answer.tool_calls_log = state.tool_calls_log
        final_answer.structured_trace = state.structured_trace
        return final_answer

    def _final_safety_check(self, answer: AgentResponse, context: OperationalContext) -> AgentResponse:
        """
        Bypass hoàn toàn việc reject recommendation do confidence < 0.35.
        Bảo toàn trọn vẹn quyết định ban đầu của LLM ở vòng ReAct 1.
        """
        if answer.recommendation is None:
            return answer

        logger.info(
            "Bypass Agent: Giữ nguyên recommendation '%s' (confidence=%s) mà không lọc qua ngưỡng safety.",
            answer.recommendation.tool_name,
            getattr(answer.recommendation, "confidence", None),
        )
        return answer
