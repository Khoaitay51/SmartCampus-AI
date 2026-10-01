"""
app/api/recommendations.py
--------------------------
AI Recommendation HITL (Human-in-the-Loop) router.
FR-AI-05: Mọi tool execution cần user confirm trên DTwin.
FR-DT-03: AI agent suggest tool → DTwin hiện popup.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user, require_role
from app.auth.models import User
from app.campus.models import AIRecommendation
from app.campus.schemas import HitlToggleRequest, RecommendationAction, RecommendationResponse
from app.database.session import get_async_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recommendations", tags=["AI Recommendations (HITL)"])


@router.get("", response_model=list[RecommendationResponse])
async def list_recommendations(
    status: str | None = "pending",
    room_id: UUID | None = None,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Liệt kê AI recommendations (mặc định pending cho HITL)."""
    query = select(AIRecommendation)
    if status:
        query = query.where(AIRecommendation.status == status)
    if room_id:
        query = query.where(AIRecommendation.room_id == room_id)

    result = await db.execute(query.order_by(AIRecommendation.created_at.desc()).limit(50))
    return result.scalars().all()


@router.post("", response_model=RecommendationResponse, status_code=201)
async def create_recommendation(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_async_db),
):
    """Internal: AI agent tạo recommendation mới.

    Được gọi từ evaluate pipeline hoặc MQTT bridge khi AI agent suggest tool.
    Không cần auth (internal service call).
    """
    rec = AIRecommendation(
        event_id=payload.get("event_id"),
        room_id=payload.get("room_id"),
        tool_name=payload["tool_name"],
        tool_params=payload.get("tool_params", {}),
        reason=payload.get("reason"),
        confidence=payload.get("confidence"),
        urgency=payload.get("urgency", "medium"),
        status="pending",
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


@router.get("/{rec_id}", response_model=RecommendationResponse)
async def get_recommendation(
    rec_id: UUID,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Xem chi tiết recommendation."""
    rec = await db.get(AIRecommendation, rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


@router.get("/hitl/status")
async def get_hitl_status():
    """Lấy trạng thái cấu hình HITL hiện tại (True = Bắt buộc duyệt tay; False = Auto-pilot)."""
    from app.campus.hitl import is_hitl_enabled
    return {"hitl_enabled": is_hitl_enabled()}


@router.post("/hitl/toggle")
async def toggle_hitl(
    payload: HitlToggleRequest | None = None,
    _user: User = Depends(require_role("admin")),
):
    """Admin bật hoặc tắt chế độ Human-in-the-Loop.
    
    Nếu không truyền enabled, tự động đảo ngược trạng thái (toggle).
    """
    from app.campus.hitl import is_hitl_enabled, set_hitl_enabled
    from app.websocket.manager import ws_manager

    req_enabled = payload.enabled if payload else None
    new_state = (not is_hitl_enabled()) if req_enabled is None else bool(req_enabled)
    set_hitl_enabled(new_state)

    # Thông báo realtime tới toàn bộ giao diện DTwin
    await ws_manager.broadcast({
        "type": "hitl_status_changed",
        "hitl_enabled": new_state,
        "changed_by": _user.username,
    })

    return {
        "hitl_enabled": new_state,
        "message": f"Chế độ HITL đã {'BẬT (Phê duyệt thủ công)' if new_state else 'TẮT (AI Tự động thực thi)'}",
    }


@router.post("/{rec_id}/execute", response_model=RecommendationResponse)
async def execute_recommendation(
    rec_id: UUID,
    data: RecommendationAction,
    current_user: User = Depends(require_role("admin", "lecturer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin/Lecturer: approve hoặc reject AI recommendation (HITL).

    FR-AI-05: Mọi tool execution cần user confirm trên DTwin khi HITL bật.
    Sau khi approve, hệ thống sẽ gửi lệnh thực thi xuống Edge Gateway
    và thiết bị phần cứng qua MQTT.
    """
    rec = await db.get(AIRecommendation, rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if rec.status != "pending":
        raise HTTPException(status_code=400, detail=f"Recommendation already {rec.status}")

    if data.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")

    rec.status = "approved" if data.action == "approve" else "rejected"
    rec.reviewed_by = current_user.id
    rec.reviewed_at = datetime.now(timezone.utc)
    rec.review_notes = data.notes

    await db.commit()
    await db.refresh(rec)

    exec_result = None
    if rec.status == "approved":
        from app.campus.hitl import dispatch_tool_execution
        # Thực thi lệnh trực tiếp sang Edge Gateway và phần cứng
        exec_result = await dispatch_tool_execution(
            rec_id=rec.id,
            room_id=rec.room_id,
            tool_name=rec.tool_name,
            tool_params=rec.tool_params,
            reason=rec.reason or "",
            operator=current_user.username,
            is_auto=False,
        )

    logger.info(
        "Recommendation %s %s by %s",
        rec_id, rec.status, current_user.username,
    )
    
    resp_obj = RecommendationResponse.model_validate(rec)
    if exec_result:
        resp_obj.execution_result = exec_result
    return resp_obj

