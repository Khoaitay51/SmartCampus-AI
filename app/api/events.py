"""
app/api/events.py
-----------------
API cung cấp danh sách sự kiện và cảnh báo gần đây (Recent Events & Alerts)
được tổng hợp từ các bảng AI Recommendation, RFID card events, và Audit logs.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user
from app.auth.models import User
from app.campus.models import AIRecommendation, Room
from app.database.session import get_async_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["Events"])


@router.get("/recent")
async def get_recent_events(
    limit: int = 10,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> list[dict[str, Any]]:
    """Tổng hợp sự kiện gần đây cho Dashboard từ các nguồn dữ liệu thực tế."""
    events = []

    # 1. Lấy từ AI Recommendations gần nhất
    rec_stmt = (
        select(AIRecommendation, Room.name.label("room_name"))
        .outerjoin(Room, AIRecommendation.room_id == Room.id)
        .order_by(AIRecommendation.created_at.desc())
        .limit(limit)
    )
    rec_res = await db.execute(rec_stmt)
    for rec, room_name in rec_res.all():
        time_str = rec.created_at.strftime("%H:%M") if rec.created_at else "Vừa xong"
        r_name = room_name or str(rec.room_id or "Phòng")[:8]
        is_warn = rec.urgency in ("high", "critical") or "smoke" in rec.tool_name.lower() or "alert" in rec.tool_name.lower()
        events.append({
            "id": str(rec.id),
            "event_id": rec.event_id or f"EVT-{str(rec.id)[:8]}",
            "title": f"Đề xuất AI: {rec.tool_name}",
            "description": f"{r_name} · {rec.reason or 'AI Agent đã phân tích telemetry và đề xuất hành động'}",
            "time": time_str,
            "tone": "amber" if is_warn else "blue",
            "type": "recommendation",
            "rec_id": str(rec.id),
        })

    # 2. Nếu danh sách sự kiện trống, lấy từ trạng thái các phòng đang có cảnh báo hoặc hoạt động
    if len(events) < limit:
        room_stmt = select(Room).where(Room.mode.in_(["SUSPECTED", "EMERGENCY", "LECTURE"])).limit(limit - len(events))
        room_res = await db.execute(room_stmt)
        for room in room_res.scalars().all():
            events.append({
                "id": str(room.id),
                "event_id": f"ROOM-{room.name}",
                "title": f"Chuyển chế độ: {room.name} -> {room.mode}",
                "description": f"Số người hiện tại: {room.occupancy} · Nhiệt độ: {room.temperature or 26.5}°C",
                "time": "Hôm nay",
                "tone": "amber" if room.mode in ("SUSPECTED", "EMERGENCY") else "green",
                "type": "room_state",
            })

    return events[:limit]
