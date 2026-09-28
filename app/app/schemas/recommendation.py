from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

ALLOWED_ACTION_TOOLS = {
    "set_fan", "fan_control",
    "set_door", "door_control",
    "set_mode", "mode_control",
    "trigger_buzzer", "buzzer_control",
    "send_alert",
    "set_led", "led_strip_control", "light_control",
}

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
    params: dict[str, Any] = Field(default_factory=dict)
    result_summary: str = ""
    level: str | None = None
    detail: str | None = None
    component: str | None = None
    ts: float | None = None


class StructuredTraceStep(BaseModel):
    step: int
    decision: str
    tool: str | None = None
    reason_code: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    observation_summary: str | None = None
    action_input: dict = Field(default_factory=dict)


class AgentResponse(BaseModel):
    event_id: UUID
    recommendation: ToolRecommendation | None = None
    alternatives: list[ToolRecommendation] = Field(default_factory=list)
    analysis: str
    skip: bool
    skip_reason: str | None = None
    tool_calls_log: list[ToolCallLogEntry] = Field(default_factory=list)
    structured_trace: list[StructuredTraceStep] = Field(default_factory=list)
    is_fallback: bool = False
    fallback_levels: list[str] = Field(default_factory=list)
    # Audit log riêng cho fallback events — KHÔNG lẫn vào tool_calls_log.
    # Chứa các entry có tool="fallback" từ FallbackTrace.to_log_entries().
    fallback_audit_log: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def fallback(
        cls,
        *,
        event_id: UUID | str,
        reason: str,
        trace: list[StructuredTraceStep] | None = None,
        recommendation: ToolRecommendation | None = None,
        alternatives: list[ToolRecommendation] | None = None,
        tool_calls_log: list[ToolCallLogEntry] | list[dict[str, Any]] | None = None,
        fallback_audit_log: list[dict[str, Any]] | None = None,
        skip: bool = True,
        skip_reason: str | None = None,
        is_fallback: bool = True,
        fallback_levels: list[str] | None = None,
    ) -> "AgentResponse":
        normalized_event_id = event_id if isinstance(event_id, UUID) else UUID(str(event_id))
        normalized_tool_calls = [
            item if isinstance(item, ToolCallLogEntry) else ToolCallLogEntry(**item)
            for item in (tool_calls_log or [])
        ]
        return cls(
            event_id=normalized_event_id,
            recommendation=recommendation,
            alternatives=alternatives or [],
            analysis=f"[FALLBACK] {reason}",
            skip=skip,
            skip_reason=skip_reason or "fallback_recovery",
            tool_calls_log=normalized_tool_calls,
            structured_trace=trace or [],
            is_fallback=is_fallback,
            fallback_levels=fallback_levels or ["rules"],
            fallback_audit_log=fallback_audit_log or [],
        )