"""
tests/test_rag_scenarios.py
---------------------------
Script thực thi và kiểm thử trực quan các kịch bản khó (Challenging Scenarios)
được định nghĩa trong tests/fixtures/test_cases_rag_challenging.json.

Mục đích:
1. Chứng minh Agent thực hiện chu trình ReAct đa bước (>= 2 bước).
2. Kiểm chứng RAG tool được gọi thật (qua HTTP mock_backend hoặc fallback thông minh).
3. In ra chi tiết: Tool đã gọi, tham số, kết quả quan sát (observation) và quyết định cuối cùng.

Cách chạy:
    # 1. Chạy mô phỏng ReAct đa bước (không cần API key):
    python tests/test_rag_scenarios.py

    # 2. Chạy với Gemini Live (nếu có GEMINI_API_KEY trong .env):
    python tests/test_rag_scenarios.py --live
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.api.evaluate import get_agent
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload
from tests.test_evaluate import MockLLM


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "test_cases_rag_challenging.json"


def load_scenarios() -> list[dict]:
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("scenarios", [])


async def run_scenario_mock_multistep(scenario: dict):
    """Chạy kịch bản qua chuỗi ReAct đa bước mô phỏng, chứng minh gọi RAG tool."""
    print("\n" + "=" * 75)
    print(f"🔹 KỊCH BẢN: {scenario['name']}")
    print(f"   ID: {scenario['id']}")
    print(f"   Mô tả: {scenario['description']}")
    print("=" * 75)

    payload = scenario["payload"]
    event = EventPayload.model_validate(payload)
    context = OperationalContext.model_validate(payload["operational_context"])
    room_id = str(event.room_id)
    event_id = str(event.event_id)

    # Chuẩn bị chuỗi ReAct đa bước tương ứng với kịch bản
    if scenario["id"] == "scenario_temp_trend_check":
        step1 = (
            f"Self-Ask: Nhiệt độ 30.8°C có đang tiếp tục tăng không?\n"
            f"Thought: Cần tra cứu dữ liệu telemetry 1 giờ qua để biết xu hướng nhiệt độ.\n"
            f"Action: get_telemetry\n"
            f"Action Input: {{\"room_id\": \"{room_id}\", \"metric\": \"temperature\", \"window\": \"1h\"}}"
        )
        step2 = (
            f"Self-Ask: Nhiệt độ dự báo có vượt ngưỡng 34°C trong 15 phút tới không?\n"
            f"Thought: Telemetry cho thấy nhiệt độ tăng liên tục, cần dự báo EWMA để đánh giá nguy cơ.\n"
            f"Action: get_predictions\n"
            f"Action Input: {{\"room_id\": \"{room_id}\", \"metric\": \"temperature\", \"horizon\": \"15m\"}}"
        )
        step3 = (
            f"Self-Ask: Đã đủ bằng chứng để kết luận chưa?\n"
            f"Thought: Cả telemetry (tăng 5.6°C) và dự báo (sẽ lên 34.5°C) đều khẳng định phòng đang quá nhiệt trong giờ học LECTURE. Bật quạt làm mát ngay.\n"
            f"Action: finish\n"
            f"Action Input: {{\"final_json\": {{\"event_id\": \"{event_id}\", \"recommendation\": {{\"tool_name\": \"set_fan\", \"tool_params\": {{\"room_id\": \"{room_id}\", \"state\": \"on\"}}, \"reason\": \"Telemetry 1h tăng liên tục và dự báo EWMA vượt 34.5 độ C trong giờ học đông người\", \"confidence\": 0.94, \"urgency\": \"high\"}}, \"analysis\": \"Nhiệt độ phòng tăng vọt và dự báo vượt ngưỡng an toàn trong giờ học. Đề xuất bật quạt thông gió làm mát.\", \"skip\": false}}}}"
        )
        review = json.dumps({"status": "Accomplished", "reasoning": "Thu thập đủ telemetry và prediction trước khi kết luận.", "suggestions": None})
        llm = MockLLM([step1, step2, step3, review])

    elif scenario["id"] == "scenario_rfid_unknown_night":
        step1 = (
            f"Self-Ask: Phòng có đang trong giờ học hợp lệ không?\n"
            f"Thought: Thẻ lạ quẹt vào phòng học vắng lúc 19:45, cần kiểm tra lịch học.\n"
            f"Action: get_schedule\n"
            f"Action Input: {{\"room_id\": \"{room_id}\", \"date\": \"today\"}}"
        )
        step2 = (
            f"Self-Ask: Phòng đã đóng cửa từ khi nào?\n"
            f"Thought: Lịch học xác nhận không có lớp ban đêm, cần xem lịch sử chuyển trạng thái phòng.\n"
            f"Action: get_room_history\n"
            f"Action Input: {{\"room_id\": \"{room_id}\", \"hours\": 6}}"
        )
        step3 = (
            f"Self-Ask: Cần đưa ra hành động gì?\n"
            f"Thought: Phòng đã khóa từ 17:30 và không có lịch học tối, quẹt thẻ lạ là dấu hiệu nghi vấn cần gửi cảnh báo an ninh.\n"
            f"Action: finish\n"
            f"Action Input: {{\"final_json\": {{\"event_id\": \"{event_id}\", \"recommendation\": {{\"tool_name\": \"send_alert\", \"tool_params\": {{\"room_id\": \"{room_id}\", \"message\": \"Phát hiện quẹt thẻ lạ ngoài giờ học tại phòng A204 đã đóng cửa\", \"level\": \"warning\"}}, \"reason\": \"Không có lịch học buổi tối và phòng đã khóa từ 17:30\", \"confidence\": 0.9, \"urgency\": \"medium\"}}, \"analysis\": \"Quẹt thẻ không hợp lệ ngoài giờ tại khu vực không có lịch học. Đề xuất gửi cảnh báo an ninh kiểm tra.\", \"skip\": false}}}}"
        )
        review = json.dumps({"status": "Accomplished", "reasoning": "Đã kiểm tra cả schedule và history trước khi cảnh báo.", "suggestions": None})
        llm = MockLLM([step1, step2, step3, review])

    else:  # scenario_smoke_first_spike
        step1 = (
            f"Self-Ask: Khói tăng lần đầu hay đã từng xảy ra gần đây?\n"
            f"Thought: Khói chớm 415 nhưng nhiệt độ bình thường (26°C), cần tra cứu lịch sử sự kiện khói trong 24h qua.\n"
            f"Action: get_room_history\n"
            f"Action Input: {{\"room_id\": \"{room_id}\", \"hours\": 24}}"
        )
        step2 = (
            f"Self-Ask: Chỉ số khói tăng đột biến hay tăng chậm?\n"
            f"Thought: Chưa có tiền sử khói trong 24h, cần kiểm tra telemetry khói 15 phút gần nhất.\n"
            f"Action: get_telemetry\n"
            f"Action Input: {{\"room_id\": \"{room_id}\", \"metric\": \"smoke\", \"window\": \"15m\"}}"
        )
        step3 = (
            f"Self-Ask: Kích hoạt còi báo động mức độ nào?\n"
            f"Thought: Khói tăng đột biến lần đầu, nhiệt độ chưa tăng, trạng thái suspected. Kích hoạt còi ngắn cảnh báo sớm, không bật còi liên tục emergency.\n"
            f"Action: finish\n"
            f"Action Input: {{\"final_json\": {{\"event_id\": \"{event_id}\", \"recommendation\": {{\"tool_name\": \"trigger_buzzer\", \"tool_params\": {{\"room_id\": \"{room_id}\", \"pattern\": \"short\"}}, \"reason\": \"Khói tăng đột biến lần đầu chạm ngưỡng suspected, phát tín hiệu còi ngắn kiểm tra\", \"confidence\": 0.85, \"urgency\": \"high\"}}, \"analysis\": \"Khói tăng chạm ngưỡng suspected lần đầu trong 24h. Kích hoạt còi ngắn cảnh báo phòng học kiểm tra.\", \"skip\": false}}}}"
        )
        review = json.dumps({"status": "Accomplished", "reasoning": "Xác minh lịch sử và mức độ khói hợp lý.", "suggestions": None})
        llm = MockLLM([step1, step2, step3, review])

    agent = get_agent(llm=llm)
    response = await agent.evaluate(event, context)

    print("\n📋 KẾT QUẢ THỰC THI RE-ACT VÀ RAG TOOLS:")
    print(f"• Số lượt RAG Tool đã thực thi: {len(response.tool_calls_log)}")
    for idx, log in enumerate(response.tool_calls_log, 1):
        print(f"  [{idx}] Tool: {log.tool}")
        print(f"      Params: {json.dumps(log.params, ensure_ascii=False)}")
        print(f"      Kết quả nhận được (Observation): {log.result_summary[:120]}...")

    print(f"\n• Chi tiết lộ trình Structured Trace ({len(response.structured_trace)} bước):")
    for step in response.structured_trace:
        print(f"  Step {step.step}: Decision='{step.decision}' | Tool='{step.tool or '-'}' | Reason='{step.reason_code}'")

    print("\n• Đề xuất cuối cùng (Final Recommendation):")
    if response.recommendation:
        print(f"  Tool: {response.recommendation.tool_name}")
        print(f"  Params: {json.dumps(response.recommendation.tool_params, ensure_ascii=False)}")
        print(f"  Confidence: {response.recommendation.confidence}")
        print(f"  Lý do: {response.recommendation.reason}")
    else:
        print(f"  Skip: {response.skip} | Lý do: {response.skip_reason}")

    print(f"• Phân tích: {response.analysis}")


async def run_scenario_live(scenario: dict):
    """Chạy kịch bản trực tiếp với Gemini LLM thật (cần GEMINI_API_KEY)."""
    print("\n" + "=" * 75)
    print(f"🌟 [GEMINI LIVE] CHẠY KỊCH BẢN THỰC TẾ: {scenario['name']}")
    print("=" * 75)

    payload = scenario["payload"]
    event = EventPayload.model_validate(payload)
    context = OperationalContext.model_validate(payload["operational_context"])

    agent = get_agent()
    print("--> Đang gửi sự kiện đến Gemini Agent, chờ chu trình ReAct...")
    response = await agent.evaluate(event, context)

    print("\n📋 KẾT QUẢ GEMINI SUY LUẬN:")
    print(f"• Số RAG Tools được Gemini gọi: {len(response.tool_calls_log)}")
    for idx, log in enumerate(response.tool_calls_log, 1):
        print(f"  [{idx}] Tool: {log.tool}")
        print(f"      Params: {json.dumps(log.params, ensure_ascii=False)}")
        print(f"      Observation trả về: {log.result_summary[:120]}...")

    print(f"\n• Lộ trình suy luận Structured Trace:")
    for step in response.structured_trace:
        print(f"  Step {step.step}: Decision='{step.decision}' | Tool='{step.tool or '-'}'")

    print(f"\n• Kết luận:")
    if response.recommendation:
        print(f"  Khuyến nghị: {response.recommendation.tool_name}")
        print(f"  Tham số: {json.dumps(response.recommendation.tool_params, ensure_ascii=False)}")
        print(f"  Độ tin cậy: {response.recommendation.confidence}")
    else:
        print(f"  Bỏ qua (Skip): {response.skip} | Lý do: {response.skip_reason}")
    print(f"• Phân tích: {response.analysis}")


async def main():
    parser = argparse.ArgumentParser(description="Chạy kiểm thử các kịch bản RAG đa bước.")
    parser.add_argument("--live", action="store_true", help="Dùng Gemini LLM thật thay vì MockLLM")
    args = parser.parse_args()

    scenarios = load_scenarios()
    print(f"Đã tải {len(scenarios)} kịch bản từ {FIXTURE_PATH}")

    for sc in scenarios:
        if args.live:
            await run_scenario_live(sc)
        else:
            await run_scenario_mock_multistep(sc)


if __name__ == "__main__":
    asyncio.run(main())
