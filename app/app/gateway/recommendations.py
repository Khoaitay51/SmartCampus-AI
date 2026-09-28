"""
gateway/recommendations.py
-----------------------------
Build và gửi recommendation lên Gateway (section 2, 3c, "Action endpoints" ở section 5).

Module này KHÔNG tự quyết định execute hay chờ approve — đó là logic của
safety/ + agent state (SELF_EXECUTE / HUMAN_INTERVENTION). Ở đây chỉ lo phần
I/O + đóng gói payload đúng contract.
"""
from __future__ import annotations
import httpx
from typing import Any, Literal
from pydantic import BaseModel, Field
from .client import GatewayClient
from app.schemas.recommendation import AgentResponse
import logging

logger = logging.getLogger(__name__)

Urgency = Literal["low", "medium", "high"]
Mode = Literal["self_execute", "human_intervention"]


class ToolCall(BaseModel):
    tool_name: str
    tool_params: dict[str, Any]
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    urgency: Urgency | None = None


class RecommendationPayload(BaseModel):
    """Response chuẩn của /evaluate — theo section 2."""

    event_id: str
    recommendation: ToolCall | None
    alternatives: list[ToolCall] = Field(default_factory=list)
    analysis: str
    skip: bool = False
    skip_reason: str | None = None
    tool_calls_log: list[dict[str, Any]] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    success: bool
    executed_at: str
    mode: Mode


class RecommendationsClient:
    def __init__(self, client: GatewayClient) -> None:
        self._client = client

    async def submit(self, payload: RecommendationPayload) -> dict[str, Any]:
        """POST /api/ai/recommend — gateway trả {"recommendation_id", "status": "pending_approval"}."""
        return await self._client.post("/ai/recommend", json=payload.model_dump(exclude_none=True))

    async def list_pending(self) -> list[dict[str, Any]]:
        """GET /api/ai/recommendations?status=pending"""
        data = await self._client.get("/ai/recommendations", params={"status": "pending"})
        return data.get("recommendations", data) if isinstance(data, dict) else data

    async def get_status(self, recommendation_id: str) -> dict[str, Any]:
        """GET /api/ai/recommendations/{id}/status"""
        return await self._client.get(f"/ai/recommendations/{recommendation_id}/status")

    async def get_mode(self) -> dict[str, Any]:
        """GET /api/ai/mode"""
        return await self._client.get("/ai/mode")

    async def set_mode(self, mode: Mode) -> dict[str, Any]:
        """POST /api/ai/mode — chuyển SELF_EXECUTE / HUMAN_INTERVENTION."""
        return await self._client.post("/ai/mode", json={"mode": mode})

    async def kill_switch(self) -> dict[str, Any]:
        """POST /api/ai/kill-switch — force về HUMAN_INTERVENTION ngay lập tức (emergency brake)."""
        return await self._client.post("/ai/kill-switch")

    async def get_audit_log(
        self, mode: str | None = None, status: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """GET /api/ai/audit-log?mode=...&status=...&limit=..."""
        params = {k: v for k, v in {"mode": mode, "status": status, "limit": limit}.items() if v is not None}
        data = await self._client.get("/ai/audit-log", params=params)
        return data.get("entries", data) if isinstance(data, dict) else data

    @staticmethod
    def build_evaluate_response(
        payload: RecommendationPayload,
        executed: bool,
        execution_result: ExecutionResult | None = None,
        pending_approval_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Đóng gói response cuối cùng cho POST /evaluate (endpoint agent tự expose,
        xem api/evaluate.py), đúng format section 3c:
        - SELF_EXECUTE: executed=true + execution_result
        - HUMAN_INTERVENTION: executed=false + pending_approval_id
        """
        body = payload.model_dump(exclude_none=True)
        body["executed"] = executed
        body["execution_result"] = execution_result.model_dump() if execution_result else None
        if pending_approval_id:
            body["pending_approval_id"] = pending_approval_id
        return body

    async def post_recommendation(event_id: str,  agent_response: AgentResponse) -> dict:

        # ep kieu du lieu noi bo thanh JSON chuan theo contract cua file AI_AGENT_INTEGRATIOn
        payload = {
            "event_id": event_id,
            "recommendation": None,
            "alternatives": [alt.model_dump() for alt in agent_response.alternatives] if agent_response.alternatives else [],
            "analysis": agent_response.analysis,
            "skip": agent_response.skip,
            "skip_reason": agent_response.skip,
        }

        if not agent_response.skip and agent_response.recommendation:
            payload["recommendation"] = {
                "tool_name": agent_response.recommendation.tool_name,
                "tool_params": agent_response.recommendation.tool_params,
                "reason": agent_response.recommendation.reason,
                "confidence": agent_response.recommendation.confidence,
                "urgency": agent_response.recommendation.urgency,
            }

        # Log payload de de dang debug audit trail
        logger.info(f"Dang gui recommendation cho event {event_id} toi Backend.")

        # Giao tiếp với FastAPI Gateway qua HTTP POST
        endpoint = f"{settings.GATEWAY_API_URL}/ai/recommend"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(endpoint, json=payload, timeout=10.0)
                response.raise_for_status()
                
                # Backend sẽ trả về trạng thái (VD: {"recommendation_id": "...", "status": "pending_approval"})
                result = response.json()
                logger.info(f"Backend phản hồi: {result['status']}")
                return result
                
            except httpx.HTTPError as e:
                logger.error(f"Lỗi khi gửi recommendation tới Gateway: {e}")
                # Xử lý retry logic hoặc ghi log error tùy vào chiến lược safety của hệ thống
                raise