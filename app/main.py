"""
app/main.py
-----------
Entrypoint chính cho FastAPI application của SmartCampus AI Service.
Bao gồm: AI Agent API + RBAC/JWT Auth + Campus Management + WebSocket MQTT Tunnel.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import evaluate, feedback, health
from app.api import auth as auth_router
from app.api import users as users_router
from app.api import devices as devices_router
from app.api import campus_rooms as rooms_router
from app.api import rfid as rfid_router
from app.api import sessions as sessions_router
from app.api import recommendations as recommendations_router
from app.websocket.router import router as ws_router
from app.database.session import init_db
from app.logging.observability import setup_observability
from app.memory.context_rollup import memory_rollup_worker
from app.websocket.mqtt_bridge import mqtt_bridge_worker

setup_observability()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup: khởi tạo database schema & khởi chạy background workers
    await init_db()
    rollup_task = asyncio.create_task(memory_rollup_worker(check_interval_seconds=3600))
    mqtt_task = asyncio.create_task(mqtt_bridge_worker())
    yield
    # 2. Shutdown: hủy tasks và chờ kết thúc an toàn
    mqtt_task.cancel()
    rollup_task.cancel()
    for task in (mqtt_task, rollup_task):
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="SmartCampus AI Agent API",
    description=(
        "AI Agent backend xử lý phân tích ngữ cảnh, suy luận ReAct, "
        "đề xuất điều khiển thiết bị, RBAC/JWT auth, và WebSocket MQTT tunnel."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — cho phép DTwin frontend truy cập
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production: restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers — AI Agent (existing)
# ---------------------------------------------------------------------------
app.include_router(health.router, tags=["Health"])
app.include_router(evaluate.router, tags=["Evaluate"])
app.include_router(feedback.router, tags=["Feedback"])

# ---------------------------------------------------------------------------
# Routers — Auth & RBAC
# ---------------------------------------------------------------------------
app.include_router(auth_router.router)

# ---------------------------------------------------------------------------
# Routers — Campus Management API
# ---------------------------------------------------------------------------
app.include_router(users_router.router)
app.include_router(devices_router.router)
app.include_router(rooms_router.router)
app.include_router(rfid_router.router)
app.include_router(sessions_router.router)
app.include_router(recommendations_router.router)

# ---------------------------------------------------------------------------
# WebSocket MQTT Tunnel
# ---------------------------------------------------------------------------
app.include_router(ws_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "SmartCampus AI Agent Service running", "version": "2.0.0"}
