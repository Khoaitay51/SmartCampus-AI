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


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]


# ---------------------------------------------------------------------------
# 1. RAG TOOLS — Công cụ tra cứu dữ liệu (chỉ đọc, Agent tự gọi trong ReAct)
# ---------------------------------------------------------------------------
RAG_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="search_history",
        description="Semantic search qua pgvector embeddings trên telemetry summaries lịch sử.",
        parameters={
            "query": "string (bắt buộc)",
            "room_id": "string (tùy chọn)",
            "time_range": "enum ['1h', '6h', '24h', '7d']",
        },
    ),
    ToolDefinition(
        name="get_telemetry",
        description="Query raw time-series data cho 1 metric cụ thể của 1 phòng.",
        parameters={
            "room_id": "string (bắt buộc)",
            "metric": "enum ['temperature', 'humidity', 'co2', 'smoke', 'occupancy']",
            "window": "enum ['15m', '1h', '6h']",
        },
    ),
    ToolDefinition(
        name="get_attendance",
        description="Query attendance records theo phòng/session/lớp.",
        parameters={
            "room_id": "string (tùy chọn)",
            "session_id": "string (tùy chọn)",
            "class_code": "string (tùy chọn)",
        },
    ),
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
    ToolDefinition(
        name="get_schedule",
        description="Query lịch học theo phòng hoặc theo ngày.",
        parameters={
            "room_id": "string (tùy chọn)",
            "date": "string (tùy chọn, YYYY-MM-DD)",
        },
    ),
    ToolDefinition(
        name="get_predictions",
        description="EWMA prediction cho 1 metric trong tương lai gần.",
        parameters={
            "room_id": "string (bắt buộc)",
            "metric": "enum ['temperature', 'co2']",
            "horizon": "enum ['15m', '30m']",
        },
    ),
]


# ---------------------------------------------------------------------------
# 2. ACTION TOOLS — Công cụ điều khiển thiết bị (được đề xuất trong finish)
# ---------------------------------------------------------------------------
ACTION_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="set_fan",
        description="Bật hoặc tắt quạt thông gió/làm mát trong phòng.",
        parameters={"room_id": "string", "state": "enum ['on', 'off']"},
    ),
    ToolDefinition(
        name="set_door",
        description="Khóa hoặc mở khóa cửa phòng học.",
        parameters={"room_id": "string", "state": "enum ['locked', 'unlocked']"},
    ),
    ToolDefinition(
        name="set_mode",
        description="Thay đổi chế độ vận hành (FSM mode) của phòng.",
        parameters={
            "room_id": "string",
            "mode": "enum ['SAVING', 'SELF_STUDY', 'LECTURE', 'EXAM', 'LOCK', 'SUSPECTED', 'EMERGENCY']",
        },
    ),
    ToolDefinition(
        name="trigger_buzzer",
        description="Kích hoạt còi báo động trong phòng học.",
        parameters={"room_id": "string", "pattern": "enum ['short', 'long', 'continuous']"},
    ),
    ToolDefinition(
        name="send_alert",
        description="Gửi thông báo cảnh báo tới giảng viên hoặc quản trị viên hệ thống.",
        parameters={
            "room_id": "string",
            "message": "string",
            "level": "enum ['info', 'warning', 'critical']",
        },
    ),
    ToolDefinition(
        name="set_led",
        description="Điều khiển đèn LED hiển thị trạng thái phòng.",
        parameters={"room_id": "string", "state": "enum ['solid', 'blink']"},
    ),
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
    "SAVING": {"set_fan", "set_door", "set_mode", "send_alert", "set_led"},
    "SELF_STUDY": {"set_fan", "set_door", "set_mode", "send_alert", "set_led"},
    "LECTURE": {"set_fan", "set_door", "set_mode", "send_alert", "set_led"},
    "EXAM": {"set_fan", "send_alert", "set_led", "set_mode"},  # Không tự ý set_door / trigger_buzzer trong giờ thi
    "LOCK": {"send_alert", "trigger_buzzer", "set_mode"},  # Giữ nguyên khóa cửa
    "SUSPECTED": {"set_fan", "send_alert", "set_led", "trigger_buzzer", "set_mode"},
    "EMERGENCY": {"set_fan", "set_door", "set_mode", "trigger_buzzer", "send_alert", "set_led"},
}


def is_tool_allowed_in_mode(tool_name: str, room_mode: str) -> bool:
    """Kiểm tra xem tool có được phép thực thi trong chế độ phòng hiện tại hay không."""
    normalized_mode = (room_mode or "").upper().strip()
    if normalized_mode in MODE_PERMISSIONS:
        return tool_name in MODE_PERMISSIONS[normalized_mode]
    return tool_name in ALLOWED_ACTION_TOOLS
