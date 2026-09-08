from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

ALLOWED_ACTION_TOOLS = {"set_fan", "set_door", "set_mode", "trigger_buzzer", "send_alert", "set_led"}

Urgency = Literal["low", "medium", "high"]


class ToolRecommendation(BaseModel):
    tool_name: str
    tool_params: dict[str, Any]
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    urgency: Urgency = "medium"

    @field_validator("tool_name")
    @classmethod
    def must_be_whitelisted(cls, v: str) -> str:
        if v not in ALLOWED_ACTION_TOOLS:
            raise ValueError(f"tool_name '{v}' không nằm trong whitelist {ALLOWED_ACTION_TOOLS}")
        return v


class ToolCallLogEntry(BaseModel):
    tool: str
    params: dict[str, Any]
    result_summary: str


class AgentResponse(BaseModel):
    event_id: UUID
    recommendation: ToolRecommendation | None = None
    alternatives: list[ToolRecommendation] = []
    analysis: str
    skip: bool
    skip_reason: str | None = None
    tool_calls_log: list[ToolCallLogEntry] = []