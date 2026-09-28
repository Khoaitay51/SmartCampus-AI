"""
app/tools/registry.py
---------------------
Định nghĩa danh sách các Tool khả dụng (RAG tools, Action tools, Finish tool),
hàm render mô tả tool cho prompt của LLM và ma trận phân quyền theo chế độ phòng (room_mode).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas.recommendation import ALLOWED_ACTION_TOOLS
from app.tools.rag import (
    SEARCH_HISTORY_TOOL,
    TELEMETRY_TOOL,
    ATTENDANCE_TOOL,
    SCHEDULE_TOOL,
    PREDICTIONS_TOOL,
)
from app.tools.actions import (
    FAN_TOOL,
    DOOR_TOOL,
    BUZZER_TOOL,
    LED_TOOL,
    ALERT_TOOL,
)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]


# ---------------------------------------------------------------------------
# 1. RAG TOOLS — Công cụ tra cứu dữ liệu (chỉ đọc, Agent tự gọi trong ReAct)
# ---------------------------------------------------------------------------
RAG_TOOLS: list[ToolDefinition] = [
    ToolDefinition(**SEARCH_HISTORY_TOOL),
    ToolDefinition(**TELEMETRY_TOOL),
    ToolDefinition(**ATTENDANCE_TOOL),
    ToolDefinition(
        name="compare_rooms",
        description="So sánh 1 metric giữa nhiều phòng trong 1 khoảng thời gian.",
        parameters={
            "room_ids": "list[string] (bắt buộc)",
            "metric": "string (bắt buộc)",
            "window": "enum ['1h', '6h', '24h']",
        },
    ),
    ToolDefinition(
        name="get_room_history",
        description="Lịch sử state transitions (FSM) của 1 phòng.",
        parameters={
            "room_id": "string (bắt buộc)",
            "hours": "integer (bắt buộc)",
        },
    ),
    ToolDefinition(**SCHEDULE_TOOL),
    ToolDefinition(**PREDICTIONS_TOOL),
]


# ---------------------------------------------------------------------------
# 2. ACTION TOOLS — Công cụ điều khiển thiết bị (được đề xuất trong finish)
# ---------------------------------------------------------------------------
ACTION_TOOLS: list[ToolDefinition] = [
    ToolDefinition(**FAN_TOOL),
    ToolDefinition(**DOOR_TOOL),
    ToolDefinition(
        name="set_mode",
        description="Thay đổi chế độ vận hành (FSM mode) của phòng.",
        parameters={
            "room_id": "string",
            "mode": "enum ['SAVING', 'SELF_STUDY', 'LECTURE', 'EXAM', 'LOCK', 'SUSPECTED', 'EMERGENCY']",
        },
    ),
    ToolDefinition(**BUZZER_TOOL),
    ToolDefinition(**ALERT_TOOL),
    ToolDefinition(**LED_TOOL),
]


# ---------------------------------------------------------------------------
# 3. FINISH TOOL — Kết thúc chu trình reasoning ReAct
# ---------------------------------------------------------------------------
FINISH_TOOL: ToolDefinition = ToolDefinition(
    name="finish",
    description="Kết thúc quá trình phân tích và đưa ra AgentResponse hoàn chỉnh dạng JSON.",
    parameters={"final_json": "AgentResponse JSON đầy đủ (skip, recommendation, analysis, ...)"},
)


# ---------------------------------------------------------------------------
# 4. Helpers: render tool desc & check room mode permissions
# ---------------------------------------------------------------------------
def render_tool_desc(tools: list[ToolDefinition]) -> str:
    """Định dạng danh sách tool thành văn bản markdown đưa vào prompt."""
    lines: list[str] = []
    for tool in tools:
        params_formatted = ", ".join(f"{k}: {v}" for k, v in tool.parameters.items())
        lines.append(f"- `{tool.name}`: {tool.description}\n  Tham số: {{{params_formatted}}}")
    return "\n".join(lines)


# Ma trận quyền hạn tool theo chế độ phòng (room_mode)
MODE_PERMISSIONS: dict[str, set[str]] = {
    "SAVING": {"set_fan", "set_door", "set_mode", "trigger_buzzer", "send_alert", "set_led"},
    "SELF_STUDY": {"set_fan", "set_door", "set_mode", "send_alert", "set_led"},
    "LECTURE": {"set_fan", "set_door", "set_mode", "send_alert", "set_led"},
    "EXAM": {"set_fan", "send_alert", "set_led", "set_mode"},  # Không tự ý set_door / trigger_buzzer trong giờ thi
    "LOCK": {"send_alert"},  # Giữ nguyên khóa cửa
    "SUSPECTED": {"set_fan", "set_door", "trigger_buzzer", "send_alert"},
    "EMERGENCY": {"set_door", "trigger_buzzer", "send_alert"},
}


def is_tool_allowed_in_mode(tool_name: str, room_mode: str) -> bool:
    """Kiểm tra xem tool có được phép thực thi trong chế độ phòng hiện tại hay không."""
    normalized_mode = (room_mode or "").upper().strip()
    if normalized_mode in MODE_PERMISSIONS:
        return tool_name in MODE_PERMISSIONS[normalized_mode]
    return tool_name in ALLOWED_ACTION_TOOLS
