from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.agent.agent import ReActXenAgent
from app.config.settings import settings
from app.fallback import build_default_fallback_llm, evaluate_with_fallback
from app.gateway.client import GatewayClient
from app.gateway.rag import execute_rag_tool
from app.gateway.rooms import RoomsClient
from app.llm import GeminiLLMClient, OllamaLLMClient
from app.logging.audit import save_audit_and_memory
from app.schemas.context import EnvironmentContext, OperationalContext
from app.schemas.events import EventPayload
from app.schemas.recommendation import AgentResponse

logger = logging.getLogger(__name__)

router = APIRouter()

EVALUATE_TIMEOUT_SECONDS = getattr(settings, "EVALUATE_TIMEOUT_SECONDS", 25)


def get_agent(
    llm: Any | None = None,
    rag_executor: Any | None = None,
    enforce_rag_guard: bool = False,
) -> ReActXenAgent:
    """Khởi tạo instance ReActXenAgent với LLM Client và RAG tool executor."""
    if llm is None:
        provider = getattr(settings, "LLM_PROVIDER", "gemini").lower()
        if provider == "ollama":
            llm = OllamaLLMClient()
        else:
            llm = build_default_fallback_llm(GeminiLLMClient)

    return ReActXenAgent(
        llm=llm,
        execute_rag_tool=rag_executor or execute_rag_tool,
        enforce_rag_guard=enforce_rag_guard,
    )


async def enrich_context_with_environment(
    event: EventPayload,
    context: OperationalContext,
    rooms_client: RoomsClient | None = None,
) -> OperationalContext:
    """Attach raw edge environment telemetry to the operational context for agent analysis."""
    if context.environment_context is not None:
        return context

    owns_client = rooms_client is None
    gateway_client: GatewayClient | None = (
        GatewayClient(timeout=settings.ENVIRONMENT_CONTEXT_TIMEOUT_SECONDS, max_retries=0)
        if owns_client
        else None
    )
    client = rooms_client or RoomsClient(gateway_client)  # type: ignore[arg-type]
    since = context.telemetry_summary.window_start

    try:
        rows = await client.get_environment(
            room_id=str(event.room_id),
            since=since,
            limit=settings.ENVIRONMENT_CONTEXT_MAX_ROWS,
        )
        environment_context = EnvironmentContext.model_validate(
            {
                "source": "edge.query_tool.get_environment",
                "since": since,
                "row_count": len(rows),
                "readings": rows,
            }
        )
        return context.model_copy(update={"environment_context": environment_context})
    except Exception as exc:
        logger.warning(
            "Không enrich được environment context từ edge query_tool: event_id=%s room_id=%s error=%s",
            event.event_id,
            event.room_id,
            exc,
        )
        return context
    finally:
        if owns_client and gateway_client is not None:
            await gateway_client.close()


@router.post("/evaluate", response_model=AgentResponse)
async def evaluate_event(payload: dict[str, Any]) -> AgentResponse:
    """Endpoint tiếp nhận sự kiện từ Gateway, chuyển cho AI Agent phân tích

    và trả về khuyến nghị điều khiển thiết bị (AgentResponse).
    """
    # 1. Validate input (hỗ trợ cả định dạng phẳng lẫn lồng nhau)
    try:
        if "event" in payload and isinstance(payload["event"], dict):
            event_dict = dict(payload["event"])
            context_dict = payload.get("operational_context") or payload.get("context") or {}
            event_dict.setdefault("operational_context", context_dict)
        else:
            event_dict = payload
            context_dict = payload.get("operational_context", {})

        event = EventPayload.model_validate(event_dict)
        context = OperationalContext.model_validate(context_dict)
        context = await enrich_context_with_environment(event, context)
        event.operational_context = context.model_dump(mode="json")

    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid payload: {e}",
        ) from e

    # 2. Create Agent
    agent = get_agent()

    # 3. Run Agent with fallback orchestrator and timeout
    try:
        async def _run_eval(ev_data: dict[str, Any]) -> dict[str, Any]:
            resp = await agent.evaluate(event=event, context=context)
            return resp.model_dump(mode="json")

        res_dict = await evaluate_with_fallback(
            event.model_dump(mode="json"),
            _run_eval,
            agent_timeout=float(EVALUATE_TIMEOUT_SECONDS),
        )
        response = AgentResponse.model_validate(res_dict)

    except asyncio.TimeoutError:
        logger.warning(
            "Agent evaluation timeout: event_id=%s",
            event.event_id,
        )
        raise HTTPException(
            status_code=504,
            detail="Agent evaluation timed out",
        )

    except Exception:
        logger.exception(
            "Agent evaluation failed: event_id=%s",
            event.event_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Agent evaluation failed",
        )

    # 4. Lưu audit trail + pgvector memory
    try:
        await save_audit_and_memory(event, response)
    except Exception as audit_err:
        logger.warning("Lưu audit log thất bại: %s", audit_err)

    # 5. Return Agent response
    return response
