"""
app/main.py
-----------
Điểm khởi chạy ứng dụng FastAPI SmartCampus AI Agent.
Bao gồm:
- Endpoint chính: POST /evaluate (cho SmartCampus AI Agent)
- Endpoint kiểm tra sức khỏe: GET /health
"""
from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.evaluate import router as evaluate_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="SmartCampus AI Agent Service",
    description="Hệ thống AI Agent tự động giám sát, reasoning (ReAct/Review/Reflect) và điều khiển thiết bị phòng học SmartCampus.",
    version="1.0.0",
)

# Cấu hình CORS cho phép gọi từ Frontend/Dashboard/DTwin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Embed routers
app.include_router(evaluate_router)


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "service": "SmartCampus-AI",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
