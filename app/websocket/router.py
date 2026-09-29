"""
app/websocket/router.py
-----------------------
WebSocket endpoint — /ws/campus

FR-DT-07: WebSocket connection persistent giữa DTwin và FastAPI.

Client workflow:
1. Connect: ws://host/ws/campus?token=JWT_TOKEN
2. Authenticate: server verify JWT từ query param
3. Subscribe rooms: client gửi {"action": "subscribe", "room_id": "..."}
4. Receive: server push telemetry, mode changes, recommendations, alerts
5. Execute HITL: client gửi {"action": "execute_recommendation", "recommendation_id": "...", "decision": "approve"}
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.auth.service import verify_access_token
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


async def _authenticate_ws(token: str | None) -> dict[str, Any] | None:
    """Verify JWT token cho WebSocket connection."""
    if not token:
        return None
    return verify_access_token(token)


async def _handle_client_message(
    websocket: WebSocket,
    message: dict[str, Any],
    user_data: dict[str, Any],
) -> None:
    """Xử lý messages từ client WebSocket.

    Supported actions:
    - subscribe: Subscribe tới room updates
    - unsubscribe: Unsubscribe khỏi room
    - ping: Health check
    - execute_recommendation: HITL approve/reject (shortcut qua WS)
    """
    action = message.get("action", "")

    if action == "subscribe":
        room_id = message.get("room_id")
        if room_id:
            ws_manager.subscribe_room(websocket, room_id)
            await ws_manager.send_personal(websocket, {
                "type": "subscribed",
                "room_id": room_id,
            })

    elif action == "unsubscribe":
        room_id = message.get("room_id")
        if room_id:
            ws_manager.unsubscribe_room(websocket, room_id)
            await ws_manager.send_personal(websocket, {
                "type": "unsubscribed",
                "room_id": room_id,
            })

    elif action == "ping":
        await ws_manager.send_personal(websocket, {
            "type": "pong",
            "active_connections": ws_manager.active_count,
        })

    elif action == "execute_recommendation":
        # HITL shortcut: approve/reject recommendation trực tiếp qua WS
        rec_id = message.get("recommendation_id")
        decision = message.get("decision", "approve")
        notes = message.get("notes")

        if not rec_id:
            await ws_manager.send_personal(websocket, {
                "type": "error",
                "message": "Missing recommendation_id",
            })
            return

        # Check role — chỉ admin/lecturer mới execute được
        role = user_data.get("role", "")
        if role not in ("admin", "lecturer"):
            await ws_manager.send_personal(websocket, {
                "type": "error",
                "message": "Insufficient permissions. Requires admin or lecturer role.",
            })
            return

        # Execute via API logic
        try:
            from app.database.session import async_session
            from app.campus.models import AIRecommendation
            from datetime import datetime, timezone
            from uuid import UUID

            async with async_session() as db:
                rec = await db.get(AIRecommendation, UUID(rec_id))
                if not rec:
                    await ws_manager.send_personal(websocket, {
                        "type": "error",
                        "message": "Recommendation not found",
                    })
                    return

                if rec.status != "pending":
                    await ws_manager.send_personal(websocket, {
                        "type": "error",
                        "message": f"Recommendation already {rec.status}",
                    })
                    return

                rec.status = "approved" if decision == "approve" else "rejected"
                rec.reviewed_at = datetime.now(timezone.utc)
                rec.review_notes = notes
                await db.commit()
                await db.refresh(rec)

                result = {
                    "type": "recommendation_result",
                    "recommendation_id": rec_id,
                    "status": rec.status,
                    "tool_name": rec.tool_name,
                    "tool_params": rec.tool_params,
                }

                # Broadcast result to all clients
                await ws_manager.broadcast(result)

                if rec.status == "approved":
                    # Also broadcast execution command
                    await ws_manager.broadcast({
                        "type": "recommendation_executed",
                        "recommendation_id": rec_id,
                        "tool_name": rec.tool_name,
                        "tool_params": rec.tool_params,
                        "room_id": str(rec.room_id) if rec.room_id else None,
                        "approved_by": user_data.get("username"),
                    })

        except Exception as e:
            logger.error("Failed to execute recommendation via WS: %s", e)
            await ws_manager.send_personal(websocket, {
                "type": "error",
                "message": f"Failed: {str(e)}",
            })

    else:
        await ws_manager.send_personal(websocket, {
            "type": "error",
            "message": f"Unknown action: {action}",
        })


@router.websocket("/ws/campus")
async def websocket_campus(
    websocket: WebSocket,
    token: str | None = Query(default=None),
):
    """WebSocket endpoint chính cho DTwin frontend.

    Authentication: JWT token qua query param ?token=xxx
    Nếu không có token → anonymous connection (view only, no HITL).
    """
    # Authenticate
    user_data: dict[str, Any] = {}
    if token:
        payload = await _authenticate_ws(token)
        if payload:
            user_data = {
                "user_id": payload.get("user_id"),
                "username": payload.get("username"),
                "email": payload.get("email"),
                "role": payload.get("role"),
            }
        else:
            await websocket.close(code=4001, reason="Invalid token")
            return

    # Connect
    await ws_manager.connect(
        websocket,
        user_id=user_data.get("user_id"),
        role=user_data.get("role"),
    )

    # Send welcome message
    await ws_manager.send_personal(websocket, {
        "type": "connected",
        "user": user_data.get("username", "anonymous"),
        "role": user_data.get("role", "viewer"),
        "active_connections": ws_manager.active_count,
    })

    try:
        while True:
            # Receive messages from client
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
                await _handle_client_message(websocket, message, user_data)
            except json.JSONDecodeError:
                await ws_manager.send_personal(websocket, {
                    "type": "error",
                    "message": "Invalid JSON",
                })
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        ws_manager.disconnect(websocket)
