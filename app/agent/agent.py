"""
agent/agent.py
"""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable, Protocol

from app.agent import prompts
from app.agent.loop import ReActLoopRunner
from app.agent.output_parser import (
    OutputParseError,
    parse_final_recommendation,
    parse_react_step,
    parse_review_output,
)
from app.agent.state import AgentRunState, StructuredTraceStep, TrajectoryStep
from app.fallback import (
    AllProvidersFailed,
    FallbackTrace,
    ParsingExhausted,
    ResilientToolExecutor,
    build_default_fallback_llm,
    evaluate_by_rules,
    fallback_trace,
    parse_recommendation,
    record,
    LEVEL_PARSING,
    LEVEL_RULES,
)
from app.gateway.rag import execute_rag_tool as default_rag_executor
from app.llm.client import LLMClient
from app.llm.gemini import GeminiLLMClient
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload
from app.schemas.recommendation import AgentResponse, ToolCallLogEntry, ToolRecommendation
from app.tools.registry import ACTION_TOOLS, FINISH_TOOL, RAG_TOOLS, is_tool_allowed_in_mode, render_tool_desc

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.35
RagToolExecutor = Callable[[str, dict, OperationalContext], Awaitable[str]]

class RagAdapter:
    def __init__(self, fn: RagToolExecutor, context: OperationalContext):
        self.fn = fn
        self.context = context

    async def call_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        res = await self.fn(tool_name, params, self.context)
        if isinstance(res, str):
            try:
                return json.loads(res)
            except Exception:
                return {"raw": res}
        return res if isinstance(res, dict) else {"result": res}


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




class ReActXenAgent:
    def __init__(
        self,
        llm: LLMClient | None = None,
        execute_rag_tool: RagToolExecutor | None = None,
        enforce_rag_guard: bool = False,
    ):
        self._llm = llm or build_default_fallback_llm(GeminiLLMClient)
        self._execute_rag_tool = execute_rag_tool or default_rag_executor
        self._runner = ReActLoopRunner(self._llm, self._execute_rag_tool)
        self._enforce_rag_guard = enforce_rag_guard

    def _create_rule_fallback_response(
        self,
        event: EventPayload,
        trace: FallbackTrace,
        reason: str,
    ) -> AgentResponse:
        record(LEVEL_RULES, f"Chuyển sang rule fallback: {reason}", "agent")
        event_dict = json.loads(event.model_dump_json())
        rule_res = evaluate_by_rules(event_dict, reason=reason)

        rec = None
        if rule_res.get("recommendation"):
            rec = ToolRecommendation(**rule_res["recommendation"])

        alts = [ToolRecommendation(**a) for a in rule_res.get("alternatives") or []]

        # tool_calls_log: chỉ chứa các tool call thực tế (rỗng khi rule fallback)
        tool_calls_log: list[ToolCallLogEntry] = [
            ToolCallLogEntry(**item) if isinstance(item, dict) else item
            for item in rule_res.get("tool_calls_log") or []
        ]

        # fallback_audit_log: gộp audit từ rules + trace, dùng list thường (không cần ToolCallLogEntry)
        audit_from_rules: list[dict] = rule_res.get("fallback_audit_log") or []
        audit_from_trace: list[dict] = trace.to_log_entries()
        # Deduplicate theo (level, detail)
        seen_audit: set[tuple] = {(e.get("level"), e.get("detail")) for e in audit_from_rules}
        deduped_trace = [e for e in audit_from_trace if (e.get("level"), e.get("detail")) not in seen_audit]
        fallback_audit_log = audit_from_rules + deduped_trace

        return AgentResponse(
            event_id=event.event_id,
            recommendation=rec,
            alternatives=alts,
            analysis=rule_res.get("analysis", f"[FALLBACK: rules] {reason}"),
            skip=rule_res.get("skip", True),
            skip_reason=rule_res.get("skip_reason", "rule_fallback"),
            tool_calls_log=tool_calls_log,
            is_fallback=True,
            fallback_levels=trace.levels or ["rules"],
            fallback_audit_log=fallback_audit_log,
        )

    async def evaluate(self, event: EventPayload, context: OperationalContext) -> AgentResponse:
        with fallback_trace() as trace:
            try:
                final_answer = await self._evaluate_internal(event, context, trace)
            except (AllProvidersFailed, ParsingExhausted) as exc:
                logger.error("Guard kích hoạt Rule Fallback (%s: %s)", type(exc).__name__, exc)
                return self._create_rule_fallback_response(event, trace, reason=str(exc))
            except Exception as exc:
                logger.error("Lỗi agent evaluation (%s: %s) -> Rule Fallback", type(exc).__name__, exc)
                return self._create_rule_fallback_response(event, trace, reason=f"{type(exc).__name__}: {exc}")

            if trace.is_fallback:
                final_answer.is_fallback = True
                final_answer.fallback_levels = trace.levels
                if not final_answer.analysis.startswith("[FALLBACK"):
                    final_answer.analysis = f"[FALLBACK: {', '.join(trace.levels)}] {final_answer.analysis}"

                # Fallback audit entries đi vào field riêng, KHÔNG nhét vào tool_calls_log
                # (tránh consumer nhầm audit metadata với tool thực tế)
                audit_entries = trace.to_log_entries()
                if audit_entries:
                    existing = getattr(final_answer, "fallback_audit_log", None) or []
                    final_answer.fallback_audit_log = existing + audit_entries

            return final_answer

    async def _evaluate_internal(
        self, event: EventPayload, context: OperationalContext, trace: FallbackTrace
    ) -> AgentResponse:
        state = AgentRunState(event=event, context=context)
        event_context = prompts.build_event_context(
            event.model_dump_json(), context.model_dump_json()
        )

        context_text_for_ltm = (
            f"Event: {event.event_type.value}. "
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

        final_answer: AgentResponse | None = None
        consecutive_parse_errors = 0
        consecutive_rag_errors = 0

        while state.round < state.max_reflect_step:
            final_answer, consecutive_parse_errors, consecutive_rag_errors = await self._react_round(
                state, event_context, resilient_executor, consecutive_parse_errors, consecutive_rag_errors
            )

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
            state.reflections.insert(0, reflection)
            state.round += 1
            state.trajectory.clear()

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
    async def _react_round(
        self,
        state: AgentRunState,
        event_context: str,
        resilient_executor: ResilientToolExecutor,
        consecutive_parse_errors: int,
        consecutive_rag_errors: int,
    ) -> tuple[AgentResponse | None, int, int]:
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

            # May raise AllProvidersFailed if all LLM providers fail
            raw_output = await self._llm.complete(system_prompt)
            try:
                step = parse_react_step(raw_output)
                consecutive_parse_errors = 0
            except OutputParseError as e:
                consecutive_parse_errors += 1
                logger.warning("Parse react step loi (lan %d): %s", consecutive_parse_errors, e)
                # Guard 3: JSON parse fail nhiều lần -> Rule Fallback
                if consecutive_parse_errors >= 3:
                    record(LEVEL_PARSING, f"JSON parse fail liên tục ({consecutive_parse_errors} lần)", "parsing")
                    raise ParsingExhausted(f"JSON parse fail liên tục {consecutive_parse_errors} lần: {e}") from e

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
                return None, consecutive_parse_errors, consecutive_rag_errors

            if step.action == "finish":
                try:
                    answer = parse_final_recommendation(step.action_input, state.event.event_id)
                except OutputParseError as e:
                    try:
                        raw_input_str = (
                            json.dumps(step.action_input, ensure_ascii=False)
                            if isinstance(step.action_input, dict)
                            else str(step.action_input)
                        )
                        outcome = await parse_recommendation(
                            raw=raw_input_str,
                            llm=self._llm,
                            default_room_id=str(state.event.room_id),
                        )
                        if outcome.data.get("skip"):
                            answer = AgentResponse(
                                event_id=state.event.event_id,
                                recommendation=None,
                                analysis="[FALLBACK: parsing] Skipped after parsing recovery",
                                skip=True,
                                skip_reason=outcome.data.get("skip_reason", "fallback_parsing_skip"),
                            )
                        else:
                            answer = AgentResponse(
                                event_id=state.event.event_id,
                                recommendation=ToolRecommendation(**outcome.data),
                                analysis=f"[FALLBACK: parsing] {outcome.data.get('reason', 'Recovered by parsing')}",
                                skip=False,
                            )
                    except Exception as p_exc:
                        consecutive_parse_errors += 1
                        if consecutive_parse_errors >= 3:
                            record(LEVEL_PARSING, f"Final recommendation parse fail: {p_exc}", "parsing")
                            raise ParsingExhausted(f"Final JSON parse fail: {p_exc}") from p_exc

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
                        return None, consecutive_parse_errors, consecutive_rag_errors

                # Guard permission (soft warn — Policy Engine sẽ enforce thực sự)
                # Agent có quyền recommend bất kỳ tool nào nếu phân tích đủ cơ sở;
                # permission matrix chỉ là gợi ý tham khảo, không hard-block ở đây.
                if answer.recommendation is not None:
                    room_mode = getattr(state.context.room, "current_mode", "NORMAL") if getattr(state.context, "room", None) else "NORMAL"
                    if not is_tool_allowed_in_mode(answer.recommendation.tool_name, room_mode):
                        logger.warning(
                            "Tool '%s' không có trong MODE_PERMISSIONS['%s'] — "
                            "recommendation vẫn được pass, Policy Engine sẽ quyết định cuối.",
                            answer.recommendation.tool_name, room_mode,
                        )

                    # Guard confidence (soft warn): chỉ cảnh báo, không block
                    # Hard stop thực sự là _final_safety_check() ở cuối
                    if answer.recommendation.confidence < CONFIDENCE_THRESHOLD:
                        logger.warning(
                            "Confidence %.2f thấp hơn ngưỡng %.2f — recommendation vẫn được pass, "
                            "Policy Engine sẽ quyết định cuối.",
                            answer.recommendation.confidence, CONFIDENCE_THRESHOLD,
                        )

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
                return answer, consecutive_parse_errors, consecutive_rag_errors

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
                observation = await resilient_executor.execute(step.action, step.action_input)
                state.rag_calls_remaining -= 1
                state.tool_calls_log.append(
                    ToolCallLogEntry(tool=step.action, params=step.action_input, result_summary=observation[:300])
                )

                if (
                    "Không thể kết nối" in observation
                    or "Lỗi từ Gateway" in observation
                    or "TOOL ERROR" in observation
                ):
                    consecutive_rag_errors += 1
                    logger.warning("RAG tool '%s' fail (lần %d): %s", step.action, consecutive_rag_errors, observation[:100])
                    # Guard 2: RAG tool fail liên tục 3 lần -> Rule Fallback
                    if consecutive_rag_errors >= 3:
                        record(LEVEL_RULES, f"RAG tool fail liên tục {consecutive_rag_errors} lần", "tool")
                        raise RuntimeError(f"RAG tool fail liên tục {consecutive_rag_errors} lần: {observation[:100]}")
                else:
                    consecutive_rag_errors = 0

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

        return None, consecutive_parse_errors, consecutive_rag_errors

    # Review Agent
    async def _review(self, state: AgentRunState, event_context: str, answer: AgentResponse):
        prompt = prompts.REVIEW_SYSTEM_PROMPT.format(
            required_rag=prompts.build_required_rag_summary(state.event.event_type),
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

    # Safety re-check cuối cùng — chỉ reject khi confidence dưới ngưỡng tối thiểu.
    # Permission enforcement là việc của Policy Engine phía sau, không tự reject ở đây.
    def _final_safety_check(self, answer: AgentResponse, context: OperationalContext) -> AgentResponse:
        if answer.recommendation is None:
            return answer

        rec = answer.recommendation
        if rec.confidence < CONFIDENCE_THRESHOLD:
            reason = f"confidence {rec.confidence} < nguong {CONFIDENCE_THRESHOLD}"
            logger.warning("Final safety check reject recommendation: %s", reason)
            answer.recommendation = None
            answer.skip = True
            answer.skip_reason = f"final_safety_check_failed: {reason}"

        return answer