"""
app/main.py
-----------
Entrypoint chính cho FastAPI application của AI Service.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api import evaluate, feedback, health
from app.database.session import init_db
from app.logging.observability import setup_observability
from app.memory.context_rollup import memory_rollup_worker

setup_observability()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup: khởi tạo database schema & khởi chạy background rollup worker
    await init_db()
    worker_task = asyncio.create_task(memory_rollup_worker(check_interval_seconds=3600))
    yield
    # 2. Shutdown: hủy task và chờ kết thúc an toàn
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="SmartCampus AI Agent API",
    description="AI Agent backend xử lý phân tích ngữ cảnh, suy luận ReAct và đề xuất điều khiển thiết bị.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health.router, tags=["Health"])
app.include_router(evaluate.router, tags=["Evaluate"])
app.include_router(feedback.router, tags=["Feedback"])



@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "SmartCampus AI Agent Service running"}
