"""
app/api/health.py
-----------------
Health check endpoint kiểm tra trạng thái hoạt động của AI Agent Service.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Trả về trạng thái hoạt động của hệ thống."""
    return {"status": "ok", "service": "smartcampus-ai-agent"}
