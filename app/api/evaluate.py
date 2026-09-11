from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.agent.agent import ReActXenAgent
from app.config.settings import settings
from app.gateway.llm_client import AnthropicLLMClient, LLMClient
from app.gateway.rag import execute_rag_tool
from app.logging.audit import save_audit_record
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload
from app.schemas.recommendation import AgentResponse

logger = logging.getLogger(__name__)

router = APIRouter()

EVALUATE_TIMEOUT_SECONDS = getattr(settings, "EVALUATE_TIMEOUT_SECONDS", 25)


def get_agent(
    llm: Any | None = None,
    rag_executor: Any | None = None,
) -> ReActXenAgent:
    """Khởi tạo instance ReActXenAgent với LLM Client và RAG tool executor."""
    return ReActXenAgent(
        llm=llm or AnthropicLLMClient(),
        execute_rag_tool=rag_executor or execute_rag_tool,
    )


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

    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid payload: {e}",
        ) from e

    # 2. Create Agent
    agent = get_agent()

    # 3. Run Agent with timeout
    try:
        response = await asyncio.wait_for(
            agent.evaluate(
                event=event,
                context=context,
            ),
            timeout=EVALUATE_TIMEOUT_SECONDS,
        )

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

    # 4. Lưu audit trail
    try:
        save_audit_record(event, response)
    except Exception as audit_err:
        logger.warning("Lưu audit log thất bại: %s", audit_err)

    # 5. Return Agent response
    return response