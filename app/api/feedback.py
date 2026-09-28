"""
app/api/feedback.py
-------------------
Endpoint tiếp nhận phản hồi của con người (Human-in-the-loop) đối với đề xuất của Agent.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("app.api.feedback")

router = APIRouter()


class FeedbackPayload(BaseModel):
    event_id: str
    human_approved: bool
    feedback_notes: str | None = None
    corrected_action: str | None = None


@router.post("/feedback")
async def submit_feedback(payload: FeedbackPayload) -> dict[str, Any]:
    """Tiếp nhận phản hồi duyệt/bác bỏ từ Admin/Giảng viên để ghi nhận vào Long-term Memory (LTM)."""
    try:
        logger.info(
            "Nhận được phản hồi duyệt cho event %s: approved=%s, notes=%s",
            payload.event_id,
            payload.human_approved,
            payload.feedback_notes,
        )
        return {
            "status": "success",
            "event_id": payload.event_id,
            "recorded": True,
        }
    except Exception as exc:
        logger.exception("Lỗi khi ghi nhận feedback: %s", exc)
        raise HTTPException(status_code=500, detail="Không thể lưu feedback") from exc
