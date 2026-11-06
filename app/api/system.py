"""
app/api/system.py
-----------------
API kiểm tra trạng thái hoạt động thực tế của toàn bộ các dịch vụ trong hệ thống SmartCampus:
- Edge Gateway API (Port 8000)
- AI Service & RAG (Port 8001)
- Mosquitto MQTT Broker (Port 1883)
- Cơ sở dữ liệu PostgreSQL / TimescaleDB
"""
from __future__ import annotations

import asyncio
import logging
import urllib.request
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.session import get_async_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["System Health"])


def _check_http(url: str, timeout: float = 2.0) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartCampus-HealthChecker/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


@router.get("/health")
async def get_system_health(
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    """Kiểm tra live status thực tế của các component phân tán."""
    edge_url = f"{settings.BACKEND_BASE_URL.rstrip('/')}/health"
    mqtt_url = f"{settings.BACKEND_BASE_URL.rstrip('/')}/mqtt_check"

    loop = asyncio.get_running_loop()
    edge_ok, mqtt_ok = await asyncio.gather(
        loop.run_in_executor(None, _check_http, edge_url),
        loop.run_in_executor(None, _check_http, mqtt_url),
    )

    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.warning("DB health check failed: %s", e)

    return {
        "edge_gateway": {
            "name": "Edge Gateway API",
            "port": 8000,
            "status": "online" if edge_ok else "offline",
        },
        "ai_service": {
            "name": "AI Service & RAG",
            "port": 8001,
            "status": "online",
        },
        "mqtt_broker": {
            "name": "Mosquitto MQTT Broker",
            "port": 1883,
            "status": "ready" if mqtt_ok else "offline",
        },
        "database": {
            "name": "PostgreSQL & TimescaleDB",
            "port": 5432,
            "status": "online" if db_ok else "offline",
        },
    }
