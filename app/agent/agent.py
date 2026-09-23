"""
agent/agent.py
"""

from __future__ import annotations

import json
import logging
from typing import Awaitable, Callable, Protocol

from app.agent import prompts
from app.agent.output_parser import (
    OutputParseError,
    parse_final_recommendation,
    parse_react_step,
    parse_review_output,
)
from app.agent.state import AgentRunState, StructuredTraceStep, TrajectoryStep
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload
from app.schemas.recommendation import AgentResponse, ToolCallLogEntry
from app.tools.registry import ACTION_TOOLS, RAG_TOOLS, FINISH_TOOL, is_tool_allowed_in_mode, render_tool_desc

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.5


async def retrieve_past_experience(current_context_text: str, top_k: int = 3) -> str:
    """
    Truy vấn pgvector LTM để tìm các quyết định đã được human_approved=True
    có bối cảnh tương tự nhất (cosine distance). Kết quả được nhét vào System Prompt
    như Dynamic Few-Shot examples.

    Trả về chuỗi rỗng nếu DB không available hoặc chưa có kinh nghiệm nào.
    """
    try:
        from app.database.session import async_session
        from app.database.models import AgentExperienceLog
        from app.gateway.embeddings import get_embedding
        from sqlalchemy import select

        query_vector = await get_embedding(current_context_text)

        async with async_session() as db:
            stmt = (
                select(AgentExperienceLog)
                .where(AgentExperienceLog.human_approved == True)  # noqa: E712
                .order_by(AgentExperienceLog.context_embedding.cosine_distance(query_vector))
                .limit(top_k)
            )
            result = await db.execute(stmt)
            past_logs = result.scalars().all()

        if not past_logs:
            return ""

        lines = ["## Kinh nghiệm từ quá khứ (Dynamic Few-Shot — được con người duyệt):"]
        for log in past_logs:
            tool_str = log.recommended_tool or "(skip)"
            lines.append(
                f"- Khi gặp sự kiện `{log.event_type}` với bối cảnh tương tự, "
                f"tôi đã dùng tool `{tool_str}` và được quản trị viên duyệt."
            )
        lines.append("(Dùng những kinh nghiệm trên để điều chỉnh reasoning, không sao chép mù quáng.)")
        return "\n".join(lines)

    except Exception as exc:
        logger.debug("Không lấy được kinh nghiệm từ LTM (không ảnh hưởng agent): %s", exc)
        return ""


class LLMClient(Protocol):
    """Bọc LLM call để dễ test/mock — implement thật dùng Google Gemini SDK ở llm_client.py."""

    async def complete(self, system_prompt: str) -> str: ...


RagToolExecutor = Callable[[str, dict, OperationalContext], Awaitable[str]]


class ReActXenAgent:
    def __init__(self, llm: LLMClient, execute_rag_tool: RagToolExecutor):
        self._llm = llm
        self._execute_rag_tool = execute_rag_tool

    async def evaluate(self, event: EventPayload, context: OperationalContext) -> AgentResponse:
        state = AgentRunState(event=event, context=context)
        event_context = prompts.build_event_context(
            event.model_dump_json(), context.model_dump_json()
        )

        # Lấy kinh nghiệm từ pgvector LTM để inject vào prompt (Dynamic Few-Shot)
        context_text_for_ltm = (
            f"Event: {event.event_type.value}. "
            f"Context: {event.operational_context}"
        )
        past_experience_str = await retrieve_past_experience(context_text_for_ltm)
        if past_experience_str:
            logger.info("Đã lấy được kinh nghiệm từ LTM, inject vào prompt.")
        state.past_experience = past_experience_str

        final_answer: AgentResponse | None = None

        while state.round < state.max_reflect_step:
            final_answer = await self._react_round(state, event_context)

            if final_answer is not None:
                review = await self._review(state, event_context, final_answer)
                if review.status == "Accomplished":
                    break
                state.reflections.append(f"[Review round {state.round}] {review.reasoning}")
            else:
                state.reflections.append(
                    f"[Round {state.round}] Vuot qua {state.max_react_step} buoc ma chua ket luan."
                )

            reflection = await self._reflect(state, event_context)
            state.reflections.insert(0, reflection)  # chèn đầu -> Theorem R.1
            state.round += 1
            state.trajectory.clear()  # bắt đầu trajectory mới cho vòng retry

        if final_answer is None:
            final_answer = AgentResponse(
                event_id=event.event_id,
                recommendation=None,
                analysis="Agent khong dat duoc ket luan dang tin cay sau nhieu vong reflect.",
                skip=True,
                skip_reason="max_reflect_step_exceeded",
                tool_calls_log=state.tool_calls_log,
            )

        final_answer = self._final_safety_check(final_answer, context)
        final_answer.tool_calls_log = state.tool_calls_log
        final_answer.structured_trace = state.structured_trace
        return final_answer

    # ReAct + Self-Ask
    async def _react_round(self, state: AgentRunState, event_context: str) -> AgentResponse | None:
        available_tools = RAG_TOOLS + ACTION_TOOLS + [FINISH_TOOL]

        for _ in range(state.max_react_step):
            step_num = len(state.structured_trace) + 1
            system_prompt = prompts.build_react_prompt(
                event_type=state.event.event_type,
                tool_desc=render_tool_desc(available_tools),
                tool_names=", ".join(t.name for t in available_tools),
                max_rag_calls=state.rag_calls_remaining,
                reflections=state.render_reflections(),
                event_context=event_context,
                scratchpad=state.render_scratchpad(),
                past_experience=getattr(state, "past_experience", ""),
            )

            raw_output = await self._llm.complete(system_prompt)
            try:
                step = parse_react_step(raw_output)
            except OutputParseError as e:
                logger.warning("Parse loi, ghi nhan va dung vong ReAct: %s", e)
                state.trajectory.append(
                    TrajectoryStep(thought="(parse error)", action="finish", action_input={}, observation=str(e))
                )
                state.structured_trace.append(
                    StructuredTraceStep(
                        step=step_num,
                        decision="parse_error",
                        reason_code="OUTPUT_PARSE_ERROR",
                        observation_summary=str(e)[:300],
                    )
                )
                return None

            if step.action == "finish":
                try:
                    answer = parse_final_recommendation(step.action_input, state.event.event_id)
                except OutputParseError as e:
                    state.trajectory.append(
                        TrajectoryStep(
                            self_ask=step.self_ask, thought=step.thought, action=step.action,
                            action_input=step.action_input, observation=f"invalid final_json: {e}",
                        )
                    )
                    state.structured_trace.append(
                        StructuredTraceStep(
                            step=step_num,
                            decision="finish",
                            reason_code="INVALID_FINAL_JSON",
                            observation_summary=f"invalid final_json: {e}",
                            action_input=step.action_input,
                        )
                    )
                    return None
                state.trajectory.append(
                    TrajectoryStep(
                        self_ask=step.self_ask, thought=step.thought, action=step.action,
                        action_input=step.action_input, observation="finished",
                    )
                )
                state.structured_trace.append(
                    StructuredTraceStep(
                        step=step_num,
                        decision="finish",
                        reason_code="GOAL_ACCOMPLISHED",
                        observation_summary="finished",
                        action_input=step.action_input,
                        evidence_ids=[str(state.event.event_id)],
                    )
                )
                return answer

            if step.action not in {t.name for t in RAG_TOOLS}:
                observation = (
                    f"'{step.action}' khong phai RAG tool hop le de goi truc tiep. "
                    f"Action tools phai duoc dong goi vao recommendation qua 'finish', "
                    f"khong goi truc tiep trong luc reasoning."
                )
                state.trajectory.append(
                    TrajectoryStep(
                        self_ask=step.self_ask, thought=step.thought, action=step.action,
                        action_input=step.action_input, observation=observation,
                    )
                )
                state.structured_trace.append(
                    StructuredTraceStep(
                        step=step_num,
                        decision="invalid_action",
                        tool=step.action,
                        reason_code="INVALID_RAG_TOOL",
                        observation_summary=observation[:300],
                        action_input=step.action_input,
                    )
                )
                continue

            if state.rag_calls_remaining <= 0:
                observation = "Da het luot goi RAG tool (gioi han 5 lan/request). Hay ket luan voi du lieu hien co."
            else:
                observation = await self._execute_rag_tool(step.action, step.action_input, state.context)
                state.rag_calls_remaining -= 1
                state.tool_calls_log.append(
                    ToolCallLogEntry(tool=step.action, params=step.action_input, result_summary=observation[:300])
                )

            state.trajectory.append(
                TrajectoryStep(
                    self_ask=step.self_ask, thought=step.thought, action=step.action,
                    action_input=step.action_input, observation=observation,
                )
            )
            state.structured_trace.append(
                StructuredTraceStep(
                    step=step_num,
                    decision="call_tool",
                    tool=step.action,
                    reason_code=step.self_ask or "RAG_TOOL_QUERY",
                    observation_summary=observation[:300],
                    action_input=step.action_input,
                    evidence_ids=[f"call_{step.action}_{step_num}"],
                )
            )

        return None  # hết max_react_step mà chưa finish

    # Review Agent
    async def _review(self, state: AgentRunState, event_context: str, answer: AgentResponse):
        prompt = prompts.REVIEW_SYSTEM_PROMPT.format(
            event_context=event_context,
            trajectory=state.render_scratchpad(),
            final_answer=answer.model_dump_json(),
        )
        raw_output = await self._llm.complete(prompt)
        try:
            return parse_review_output(raw_output)
        except OutputParseError as e:
            logger.warning("Review parse loi, coi nhu Not Accomplished: %s", e)
            from app.agent.output_parser import ReviewResult

            return ReviewResult(status="Not Accomplished", reasoning=str(e), suggestions=None)

    # Reflect Agent
    async def _reflect(self, state: AgentRunState, event_context: str) -> str:
        prompt = prompts.REFLECT_SYSTEM_PROMPT.format(
            event_context=event_context,
            trajectory=state.render_scratchpad(),
            review_feedback=state.reflections[-1] if state.reflections else "(none)",
        )
        return await self._llm.complete(prompt)

    # Safety re-check cuối cùng
    def _final_safety_check(self, answer: AgentResponse, context: OperationalContext) -> AgentResponse:
        if answer.recommendation is None:
            return answer

        rec = answer.recommendation
        room_mode = context.room.current_mode

        violates_permission = not is_tool_allowed_in_mode(rec.tool_name, room_mode)
        violates_confidence = rec.confidence < CONFIDENCE_THRESHOLD

        if violates_permission or violates_confidence:
            reason = (
                f"tool '{rec.tool_name}' khong duoc phep trong mode '{room_mode}'"
                if violates_permission
                else f"confidence {rec.confidence} < nguong {CONFIDENCE_THRESHOLD}"
            )
            logger.warning("Final safety check reject recommendation: %s", reason)
            answer.recommendation = None
            answer.skip = True
            answer.skip_reason = f"final_safety_check_failed: {reason}"

        return answer