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
from app.campus.schemas import RecommendationAction, RecommendationResponse
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


@router.post("/{rec_id}/execute", response_model=RecommendationResponse)
async def execute_recommendation(
    rec_id: UUID,
    data: RecommendationAction,
    current_user: User = Depends(require_role("admin", "lecturer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin/Lecturer: approve hoặc reject AI recommendation (HITL).

    FR-AI-05: Mọi tool execution cần user confirm trên DTwin.
    Sau khi approve, WebSocket manager sẽ broadcast kết quả
    về MQTT để actuator thực thi.
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

    if rec.status == "approved":
        # Broadcast approved recommendation via WebSocket → MQTT
        from app.websocket.manager import ws_manager
        await ws_manager.broadcast({
            "type": "recommendation_executed",
            "recommendation_id": str(rec.id),
            "tool_name": rec.tool_name,
            "tool_params": rec.tool_params,
            "room_id": str(rec.room_id) if rec.room_id else None,
            "approved_by": current_user.username,
        })

    logger.info(
        "Recommendation %s %s by %s",
        rec_id, rec.status, current_user.username,
    )
    return rec
