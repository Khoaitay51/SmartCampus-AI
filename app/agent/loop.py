"""
app/agent/loop.py
-----------------
Quản lý vòng lặp suy luận ReAct (Reasoning & Acting), gọi tool và theo dõi trajectory steps.
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from app.agent import prompts
from app.agent.output_parser import (
    OutputParseError,
    parse_final_recommendation,
    parse_react_step,
    parse_review_output,
)
from app.agent.state import AgentRunState, StructuredTraceStep, TrajectoryStep
from app.llm.client import LLMClient
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload
from app.schemas.recommendation import AgentResponse, ToolCallLogEntry
from app.tools.registry import ACTION_TOOLS, FINISH_TOOL, RAG_TOOLS, is_tool_allowed_in_mode, render_tool_desc

logger = logging.getLogger("app.agent.loop")

CONFIDENCE_THRESHOLD = 0.5
MAX_REACT_STEP = 6
MAX_REFLECT_STEP = 3
MAX_RAG_CALLS = 5

RagToolExecutor = Callable[[str, dict, OperationalContext], Awaitable[str]]


class ReActLoopRunner:
    def __init__(self, llm: LLMClient, execute_rag_tool: RagToolExecutor):
        self.llm = llm
        self.execute_rag_tool = execute_rag_tool

    async def run(
        self,
        event: EventPayload,
        context: OperationalContext,
        state: AgentRunState,
        past_experience_str: str = "",
    ) -> AgentResponse:
        event_context = prompts.build_event_context(
            event.model_dump_json(), context.model_dump_json()
        )

        system_prompt = prompts.build_react_system_prompt(
            event_context=event_context,
            rag_tools_desc=render_tool_desc(RAG_TOOLS),
            action_tools_desc=render_tool_desc(ACTION_TOOLS),
            finish_tool_desc=render_tool_desc([FINISH_TOOL]),
            past_experience=past_experience_str,
        )

        rag_calls_count = 0

        while state.current_step < MAX_REACT_STEP:
            state.current_step += 1
            full_prompt = prompts.format_react_iteration_prompt(
                system_prompt, state.history_formatted
            )

            try:
                llm_output = await self.llm.complete(full_prompt)
            except Exception as exc:
                logger.error("LLM complete call error step %d: %s", state.current_step, exc)
                break

            step_parsed = parse_react_step(llm_output)
            trace_entry = StructuredTraceStep(
                step_number=state.current_step,
                thought=step_parsed.thought,
                action=step_parsed.action,
                action_input=step_parsed.action_input,
            )

            if isinstance(step_parsed, OutputParseError):
                state.add_step(
                    TrajectoryStep(
                        thought=llm_output,
                        observation=f"SYSTEM ERROR: Không parse được output ({step_parsed.raw_error}). Hãy trả về theo đúng định dạng Thought/Action/Action Input!",
                    ),
                    trace_entry=trace_entry,
                )
                continue

            if step_parsed.action == "finish":
                recommendation = parse_final_recommendation(step_parsed.action_input)
                recommendation.trace = state.structured_trace

                confidence = recommendation.confidence
                recommendation.risk_assessment.low_confidence_flag = confidence < CONFIDENCE_THRESHOLD

                needs_reflection = False
                reflect_reason = ""
                if confidence < CONFIDENCE_THRESHOLD:
                    needs_reflection = True
                    reflect_reason = f"Độ tự tin ({confidence:.2f}) quá thấp (< {CONFIDENCE_THRESHOLD})"
                elif recommendation.recommendation and recommendation.recommendation.tool:
                    tool_name = recommendation.recommendation.tool
                    if not is_tool_allowed_in_mode(tool_name, context.room_mode.value):
                        needs_reflection = True
                        reflect_reason = (
                            f"Tool `{tool_name}` KHÔNG được phép thực thi trong chế độ phòng `{context.room_mode.value}`!"
                        )

                if needs_reflection and state.reflect_step < MAX_REFLECT_STEP:
                    state.reflect_step += 1
                    logger.warning("Kích hoạt Self-Reflection (lần %d): %s", state.reflect_step, reflect_reason)

                    reflect_system_prompt = prompts.build_reflection_prompt(
                        event_context=event_context,
                        trajectory_history=state.history_formatted,
                        candidate_json=step_parsed.action_input,
                        reflect_reason=reflect_reason,
                    )
                    try:
                        reviewed_output = await self.llm.complete(reflect_system_prompt)
                        revised_rec = parse_review_output(reviewed_output, default_fallback=recommendation)
                        revised_rec.trace = state.structured_trace
                        return revised_rec
                    except Exception as ref_exc:
                        logger.error("Self-reflection thất bại: %s", ref_exc)

                return recommendation

            if rag_calls_count >= MAX_RAG_CALLS:
                obs = f"SYSTEM ERROR: Đã đạt giới hạn tối đa {MAX_RAG_CALLS} lần gọi RAG tool. Hãy dùng tool 'finish' để đưa ra quyết định ngay!"
            else:
                rag_calls_count += 1
                try:
                    obs = await self.execute_rag_tool(step_parsed.action, step_parsed.action_input, context)
                except Exception as exc:
                    obs = f"TOOL ERROR: Lỗi khi thực thi tool '{step_parsed.action}': {exc}"

            state.add_step(
                TrajectoryStep(
                    thought=step_parsed.thought,
                    action=step_parsed.action,
                    action_input=step_parsed.action_input,
                    observation=obs,
                ),
                trace_entry=trace_entry,
                tool_log=ToolCallLogEntry(
                    tool_name=step_parsed.action,
                    args=step_parsed.action_input,
                    result_summary=obs[:200],
                ),
            )

        logger.warning("Đã chạm giới hạn ReAct steps (%d). Đang tạo fallback recommendation...", MAX_REACT_STEP)
        return AgentResponse.fallback(
            event_id=event.event_id,
            reason=f"Đã đạt giới hạn tối đa {MAX_REACT_STEP} bước suy luận mà chưa ra kết quả.",
            trace=state.structured_trace,
        )
