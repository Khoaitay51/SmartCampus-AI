"""
app/main.py
-----------
Entrypoint chính cho FastAPI application của AI Service.
"""
from __future__ import annotations

from fastapi import FastAPI

from app.api import evaluate, feedback, health
from app.logging.observability import setup_observability

setup_observability()

app = FastAPI(
    title="SmartCampus AI Agent API",
    description="AI Agent backend xử lý phân tích ngữ cảnh, suy luận ReAct và đề xuất điều khiển thiết bị.",
    version="1.0.0",
)

app.include_router(health.router, tags=["Health"])
app.include_router(evaluate.router, tags=["Evaluate"])
app.include_router(feedback.router, tags=["Feedback"])


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "SmartCampus AI Agent Service running"}
