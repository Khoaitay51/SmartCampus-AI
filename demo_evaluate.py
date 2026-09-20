"""
demo_evaluate.py
----------------
Kịch bản chạy thử nghiệm (Demo script) đánh giá hoạt động của SmartCampus AI Agent
với các Tool giả lập (Mock RAG Tools & Action Tools).
"""
from __future__ import annotations

import asyncio
import json
import sys
from uuid import uuid4

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent.agent import ReActXenAgent
from app.agent.output_parser import parse_final_recommendation
from app.gateway.rag import execute_rag_tool
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload


class MockDemoLLM:
    """Mock LLM phản hồi linh hoạt theo kịch bản sự kiện để demo không cần GEMINI_API_KEY."""

    def __init__(self, room_id: str, mode: str) -> None:
        self.room_id = room_id
        self.mode = mode
        self.call_count = 0

    async def complete(self, prompt: str) -> str:
        self.call_count += 1
        
        # Nếu đang ở vòng Review (kiểm tra prompt xem có chứa Review system prompt không)
        if "Reviewer Agent" in prompt or "Accomplished" in prompt or "đạt mục tiêu" in prompt.lower():
            return json.dumps({
                "status": "Accomplished",
                "reasoning": f"Đánh giá hoàn tất: Khuyến nghị phù hợp với quy định của chế độ {self.mode}.",
                "suggestions": None,
            })

        # Phản hồi cho ReAct round 1
        if "temperature_anomaly" in prompt:
            final_json = {
                "event_id": str(uuid4()),
                "recommendation": {
                    "tool_name": "set_fan",
                    "tool_params": {"room_id": self.room_id, "state": "on"},
                    "reason": "Nhiệt độ phòng tăng cao (32.5°C), cần bật quạt thông gió làm mát.",
                    "confidence": 0.90,
                    "urgency": "medium",
                },
                "analysis": "Nhiệt độ phòng đo được 32.5°C vượt ngưỡng 30°C trong giờ học. Tiến hành bật quạt làm mát.",
                "skip": False,
            }
            return (
                "Self-Ask: Nhiệt độ phòng vượt quá mức bình thường, cần làm gì?\n"
                "Thought: Tra cứu lịch sử nhiệt độ và đề xuất bật quạt thông gió.\n"
                "Action: finish\n"
                f"Action Input: {{\"final_json\": {json.dumps(final_json)}}}"
            )

        elif "smoke_detected" in prompt:
            final_json = {
                "event_id": str(uuid4()),
                "recommendation": {
                    "tool_name": "trigger_buzzer",
                    "tool_params": {"room_id": self.room_id, "pattern": "emergency"},
                    "reason": "Cảm biến phát hiện khói bất thường, kích hoạt báo động khẩn cấp.",
                    "confidence": 0.98,
                    "urgency": "high",
                },
                "analysis": "Phát hiện khói bất thường trong phòng. Cần kích hoạt buzzer báo động khẩn cấp và sơ tán.",
                "skip": False,
            }
            return (
                "Self-Ask: Có khói xuất hiện trong phòng, cần kích hoạt cảnh báo gì?\n"
                "Thought: Phát hiện khói, kích hoạt buzzer pattern emergency và thông báo khẩn.\n"
                "Action: finish\n"
                f"Action Input: {{\"final_json\": {json.dumps(final_json)}}}"
            )

        # Default fallback finish
        default_json = {
            "skip": True,
            "skip_reason": "normal_telemetry",
            "analysis": "Chỉ số phòng bình thường, không cần can thiệp thiết bị.",
        }
        return (
            "Self-Ask: Kiểm tra trạng thái hệ thống.\n"
            "Thought: Mọi chỉ số đều trong mức cho phép.\n"
            "Action: finish\n"
            f"Action Input: {{\"final_json\": {json.dumps(default_json)}}}"
        )


async def run_scenario(scenario_name: str, event_type: str, mode: str, event_data: dict):
    print("=" * 70)
    print(f"KICH BAN MO PHONG: {scenario_name}")
    print(f"   - Event Type: {event_type}")
    print(f"   - Room Mode : {mode}")
    print("=" * 70)

    room_id = str(uuid4())
    event_id = str(uuid4())

    event = EventPayload.model_validate({
        "event_id": event_id,
        "event_type": event_type,
        "room_id": room_id,
        "timestamp": "2026-09-15T09:30:00Z",
        "event_data": event_data,
        "operational_context": {
            "room": {
                "room_id": room_id,
                "room_name": "Phòng Thí Nghiệm B204",
                "room_type": "lab",
                "current_mode": mode,
                "smoke_state": "normal" if event_type != "smoke_detected" else "warning",
            },
            "telemetry_summary": {
                "window_start": "2026-09-15T08:30:00Z",
                "window_end": "2026-09-15T09:30:00Z",
                "temperature": {"min": 25.0, "max": 32.5, "avg": 29.1, "latest": event_data.get("measured_temp", 26.0)},
                "humidity": {"min": 55.0, "max": 70.0, "avg": 62.0, "latest": 65.0},
                "co2": {"min": 400.0, "max": 900.0, "avg": 650.0, "latest": 850.0},
                "smoke_value": {"min": 0.0, "max": 0.08, "avg": 0.02, "latest": event_data.get("smoke_val", 0.01)},
                "air_quality": {"min": 75.0, "max": 90.0, "avg": 82.0, "latest": 80.0},
            },
            "occupancy": {
                "current_count": 30,
                "total_in": 35,
                "total_out": 5,
                "trend": "phong hoc",
            },
            "recent_events": [],
        },
    })

    context = OperationalContext.model_validate(event.operational_context)

    mock_llm = MockDemoLLM(room_id=room_id, mode=mode)
    agent = ReActXenAgent(llm=mock_llm, execute_rag_tool=execute_rag_tool)

    print("[*] Agent đang phân tích sự kiện (Observe -> Think -> Act)...")
    response = await agent.evaluate(event, context)

    print("\n[+] KẾT QUẢ ĐÁNH GIÁ TỪ AGENT (AgentResponse):")
    print(f"   - Event ID     : {response.event_id}")
    print(f"   - Skip Action  : {response.skip} (Reason: {response.skip_reason})")
    print(f"   - Phân tích    : {response.analysis}")

    if response.recommendation:
        rec = response.recommendation
        print(f"   - Khuyến nghị  : Tool `{rec.tool_name}`")
        print(f"   - Tham số      : {rec.tool_params}")
        print(f"   - Lý do        : {rec.reason}")
        print(f"   - Độ tin cậy   : {rec.confidence * 100}% | Urgency: {rec.urgency}")

    print("\n[#] Nhật ký Tool Calls (Tool Calls Log):")
    for log_entry in response.tool_calls_log:
        print(f"   * [{log_entry.tool}] -> {log_entry.params}")
        print(f"     Tóm tắt: {log_entry.result_summary[:120]}...")

    print("\n" + "-" * 70 + "\n")


async def main():
    print("=== BAT DAU CHAY DEMO THU NGHIEM AGENT VOI MOCK TOOLS ===\n")
    
    # Kịch bản 1: Quá nhiệt trong giờ học (LECTURE mode -> cho phép set_fan)
    await run_scenario(
        scenario_name="Cảnh báo quá nhiệt trong lớp học (Mode LECTURE)",
        event_type="temperature_anomaly",
        mode="LECTURE",
        event_data={"measured_temp": 32.5},
    )

    # Kịch bản 2: Khói bất thường trong giờ tự học (EMERGENCY/SUSPECTED mode -> cho phép trigger_buzzer)
    await run_scenario(
        scenario_name="Phát hiện khói bất thường trong phòng (Mode SUSPECTED)",
        event_type="smoke_detected",
        mode="SUSPECTED",
        event_data={"smoke_val": 0.08},
    )


if __name__ == "__main__":
    asyncio.run(main())
