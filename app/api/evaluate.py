from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, HTTPExeception
from fastapi import APIRouter

from app.agent.agent import ReActXenAgent
from app.gateway.llm_client import AnthropicLLMClient
from app.gateway.rag import execute_rag_tool
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayLoad
from app.schemas.recommendation import AgentResponse

logger = logging.getLogger(__name__)
router = APIRouter()

EVALUATE_TIMEOUT_SECONDS = 25 # GATEWAY doi toi da 25 cho timeout tong cua 1 lan evaluate

def get_agent() -> ReActXenAgent:
    return ReActXenAgent(llm=AnthropicLLMClient(), execute_rag_tool=execute_rag_tool)

def _finish(event: EventPayLoad, response: AgentResponse) -> AgentResponse:
    return response

@router.post("/evaluate", response_model=AgentResponse)
async def evaluate_event(payload: dict) -> AgentResponse:
    try:
        event = EventPayLoad.model_validate(payload)
        context = OperationalContext.model_validate(payload.get("operational_context", {}))
    except Exception as e:
        raise HTTPExeception(status_code=422, detail=f"Payload khong hop le: {e}") from execute_rag_tool

    agent = get_agent()
