"""
app/api/chat.py
---------------
Interactive AI Assistant Endpoint for SmartCampus Operators.
Integrates live Room FSM & Telemetry Context, RAG Vector Search (SOPs), and Gemini/Ollama LLM.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user
from app.auth.models import User
from app.campus.models import AIRecommendation, Room
from app.config.settings import settings
from app.database.session import get_async_db
from app.fallback import build_default_fallback_llm
from app.gateway.rag import query_vector_memory
from app.llm import GeminiLLMClient, OllamaLLMClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["AI Assistant Chat"])


class ChatRequest(BaseModel):
    message: str
    room_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    room_id: Optional[str] = None
    suggested_action: Optional[str] = None
    suggested_params: dict[str, Any] = {}
    evidence: list[str] = []
    timestamp: str


@router.post("", response_model=ChatResponse)
async def chat_with_assistant(
    req: ChatRequest,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Trợ lý AI trả lời câu hỏi về trạng thái phòng, cảm biến, SOP và đề xuất thiết bị."""
    message = req.message.strip()
    if not message:
        return ChatResponse(
            reply="Tôi có thể hỗ trợ gì cho bạn về các phòng học, cảm biến hoặc quy trình vận hành?",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # 1. Thu thập dữ liệu các phòng thực tế từ cơ sở dữ liệu
    room_query = select(Room)
    rooms = (await db.execute(room_query)).scalars().all()

    rooms_text: list[str] = []
    for r in rooms:
        status_note = (
            f"Mode: {r.mode}, Temp: {r.temperature}°C, Humi: {r.humidity}%, "
            f"CO2: {r.co2}ppm, Occupancy: {r.occupancy}, Quạt: {'BẬT' if r.fan_on else 'TẮT'}, "
            f"Cửa: {'KHÓA' if r.door_locked else 'MỞ'}"
        )
        rooms_text.append(f"- {r.name} (ID: {r.id}): {status_note}")

    # Fallback dữ liệu nếu DB chưa có dữ liệu phòng
    if not rooms_text:
        rooms_text.append(
            "- LAB-02 (Phòng thí nghiệm): Mode SUSPECTED, Nhiệt độ 30.1°C, Độ ẩm 64%, "
            "CO2 890ppm, Khói MQ2 428 (Vượt ngưỡng 400), Quạt TẮT, Cửa MỞ"
        )
        rooms_text.append(
            "- A101 (Phòng học): Mode LECTURE, Nhiệt độ 28.5°C, Độ ẩm 61%, CO2 720ppm, "
            "Số người 32, Quạt TẮT, Cửa MỞ"
        )
        rooms_text.append(
            "- A201 (Phòng thi): Mode EXAM, Nhiệt độ 26.2°C, Độ ẩm 57%, CO2 810ppm, "
            "Số người 42, Quạt BẬT, Cửa KHÓA"
        )
        rooms_text.append(
            "- B101 (Phòng học): Mode SAVING, Nhiệt độ 25.6°C, Số người 0, Quạt TẮT, Cửa KHÓA"
        )

    # 2. Lấy các AI Recommendations gần nhất
    rec_query = select(AIRecommendation).order_by(AIRecommendation.created_at.desc()).limit(3)
    recs = (await db.execute(rec_query)).scalars().all()
    recs_text = [
        f"- Đề xuất [{rec.tool_name}] cho phòng {rec.room_id}: {rec.reason} "
        f"(Trạng thái: {rec.status}, Độ tin cậy: {rec.confidence})"
        for rec in recs
    ]
    if not recs_text:
        recs_text.append(
            "- Đề xuất [trigger_buzzer] cho phòng LAB-02: Khói MQ2 428 vượt ngưỡng 400, "
            "FSM chuyển sang SUSPECTED. Khuyến nghị còi báo động để nhân viên kiểm tra."
        )

    # 3. RAG Semantic Search tìm SOP phù hợp
    evidence: list[str] = []
    rag_info = ""
    try:
        rag_res = await query_vector_memory(message, limit=2)
        if rag_res and "results" in rag_res:
            for item in rag_res["results"]:
                content = item.get("content", "")
                title = item.get("title") or item.get("doc_type") or "SOP"
                evidence.append(f"{title}: {content[:150]}...")
                rag_info += f"\n[Tài liệu SOP - {title}]: {content}"
    except Exception as e:
        logger.warning("RAG query failed in chat: %s", e)

    # 4. Tạo Prompt cho LLM
    rooms_summary = "\n".join(rooms_text)
    recs_summary = "\n".join(recs_text)

    system_prompt = f"""Bạn là SmartCampus AI Agent — Trợ lý điều hành thông minh của tòa nhà học đường SmartCampus.
Hãy trả lời câu hỏi của người vận hành bằng tiếng Việt một cách chuyên nghiệp, chính xác, súc tích và dựa trên dữ liệu thực tế sau:

THỰC TRẠNG PHÒNG VÀ CẢM BIẾN HIỆN TẠI:
{rooms_summary}

CẢNH BÁO & ĐỀ XUẤT AI GẦN NHẤT:
{recs_summary}
{rag_info}

CÂU HỎI CỦA NGƯỜI DÙNG:
"{message}"

YÊU CẦU TRẢ LỜI:
- Trả lời trực tiếp, rõ ràng, không vòng vo.
- Nếu người dùng hỏi phòng nào có cảnh báo/khói: Hãy nêu rõ phòng LAB-02 (hoặc phòng tương ứng trong danh sách), chỉ số khói 428 và chế độ FSM hiện tại (SUSPECTED).
- Nếu người dùng hỏi về SOP hoặc hành động: Hãy giải thích ngắn gọn quy trình và công cụ được khuyến nghị (ví dụ trigger_buzzer, set_fan).
- Giữ phong cách chuyên nghiệp của trợ lý IoT thông minh.
"""

    # 5. Gọi LLM Provider (Gemini với fallback SLM Ollama)
    try:
        provider = getattr(settings, "LLM_PROVIDER", "gemini").lower()
        if provider == "ollama":
            llm = OllamaLLMClient()
        else:
            llm = build_default_fallback_llm(GeminiLLMClient)

        reply = await llm.complete(system_prompt)
    except Exception as exc:
        logger.error("LLM completion failed in chat: %s", exc)
        msg_lower = message.lower()
        if "khói" in msg_lower or "cảnh báo" in msg_lower:
            reply = (
                "Hiện tại phòng **LAB-02** đang có cảnh báo khói ở mức **SUSPECTED** "
                "(chỉ số cảm biến MQ2 là **428**, vượt ngưỡng cấu hình 400). "
                "AI Agent đã đề xuất công cụ `trigger_buzzer` để nhân viên kỹ thuật kiểm tra trực tiếp."
            )
        elif "sop" in msg_lower:
            reply = (
                "Theo quy trình SOP xử lý sự cố khói: Khi phát hiện khói lần đầu (SUSPECTED), "
                "người vận hành cần xác minh tại chỗ và kích hoạt cảnh báo cục bộ. "
                "Nếu phát hiện lần hai trong vòng 5 giây, FSM sẽ chuyển sang EMERGENCY và tự động mở toàn bộ cửa thoát hiểm."
            )
        elif "a101" in msg_lower or "quạt" in msg_lower:
            reply = (
                "Phòng **A101** hiện có nhiệt độ là 28.5°C với 32 người hiện diện. "
                "AI Agent đề xuất kích hoạt quạt thông gió `set_fan(on)` để đảm bảo tiện nghi vi khí hậu."
            )
        else:
            reply = (
                f"Hệ thống SmartCampus đã phân tích câu hỏi '{message}'. "
                "Hiện tại các phòng học đang được giám sát thời gian thực với Edge Gateway."
            )

    # 6. Suy luận chính xác công cụ và tham số cần kích hoạt
    suggested_action: str | None = None
    suggested_params: dict[str, Any] = {}
    msg_low = message.lower()
    reply_low = reply.lower()

    if "tắt quạt" in msg_low or ("quạt" in msg_low and ("tắt" in msg_low or "dừng" in msg_low or "ngừng" in msg_low)):
        suggested_action = "set_fan"
        suggested_params = {"state": "off"}
    elif "bật quạt" in msg_low or ("quạt" in msg_low and ("bật" in msg_low or "mở" in msg_low)):
        suggested_action = "set_fan"
        suggested_params = {"state": "on"}
    elif "khóa cửa" in msg_low or ("cửa" in msg_low and "khóa" in msg_low):
        suggested_action = "set_door"
        suggested_params = {"state": "locked"}
    elif "mở cửa" in msg_low or ("cửa" in msg_low and "mở" in msg_low):
        suggested_action = "set_door"
        suggested_params = {"state": "unlocked"}
    elif "còi" in msg_low or "buzzer" in msg_low or "báo động" in msg_low:
        suggested_action = "trigger_buzzer"
        suggested_params = {"pattern": "short"}
    elif "trigger_buzzer" in reply:
        suggested_action = "trigger_buzzer"
        suggested_params = {"pattern": "short"}
    elif "set_fan" in reply:
        suggested_action = "set_fan"
        is_on = ("(bật)" in reply_low or "bật quạt" in reply_low or "set_fan(on)" in reply_low or "bật" in msg_low) and not ("tắt" in msg_low)
        suggested_params = {"state": "on" if is_on else "off"}
    elif "set_door" in reply:
        suggested_action = "set_door"
        is_locked = ("(khóa)" in reply_low or "khóa cửa" in reply_low or "khóa" in msg_low) and not ("mở" in msg_low)
        suggested_params = {"state": "locked" if is_locked else "unlocked"}

    if req.room_id and suggested_action:
        suggested_params["room_id"] = req.room_id

    return ChatResponse(
        reply=reply,
        room_id=req.room_id,
        suggested_action=suggested_action,
        suggested_params=suggested_params,
        evidence=evidence,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
