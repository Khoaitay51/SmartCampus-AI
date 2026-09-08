from typing import Any, Optional

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    tool_name: str
    tool_params: dict[str, Any] = Field(default_factory=dict)


class ToolCallResult(BaseModel):
    tool_name: str
    success: bool
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class ToolCallLog(BaseModel):
    tool_name: str
    tool_params: dict[str, Any] = Field(default_factory=dict)
    success: bool
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None