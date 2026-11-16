"""
app/api/campus_rooms.py
-----------------------
Room management router — CRUD + FSM state + realtime sensor update.
FR-FSM-01..05.
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user, require_role
from app.auth.models import User
from app.campus.models import Room
from app.campus.schemas import RoomCreate, RoomResponse, RoomStateUpdate
from app.database.session import get_async_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rooms", tags=["Rooms"])


async def _dispatch_room_command_via_edge(
    room_id: UUID,
    command_type: str,
    command_value: str,
    reason: str,
) -> None:
    """Validate and execute room command through Edge FSM before updating Backend state/MQTT."""
    import httpx
    from app.campus.hitl import edge_internal_headers
    from app.config.settings import settings

    base_edge_url = settings.BACKEND_BASE_URL.rstrip("/")
    edge_exec_url = (
        f"{base_edge_url}/commands/room/execute"
        if base_edge_url.endswith("/api")
        else f"{base_edge_url}/api/commands/room/execute"
    )
    payload = {
        "room_id": str(room_id),
        "command_type": command_type,
        "command_value": command_value,
        "reason": reason,
        "source": "dtwin_admin",
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(edge_exec_url, json=payload, headers=edge_internal_headers())
    except Exception as exc:
        logger.warning("Edge Gateway không phản hồi khi %s=%s: %s", command_type, command_value, exc)
        raise HTTPException(
            status_code=503,
            detail=f"Edge Gateway unavailable while validating {command_type}={command_value}",
        ) from exc

    if resp.status_code in (200, 202):
        return

    try:
        detail = resp.json().get("detail", resp.text)
    except ValueError:
        detail = resp.text
    raise HTTPException(status_code=resp.status_code, detail=detail)


@router.get("", response_model=list[RoomResponse])
async def list_rooms(
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Liệt kê tất cả rooms."""
    result = await db.execute(select(Room).order_by(Room.name))
    return result.scalars().all()


@router.post("", response_model=RoomResponse, status_code=201)
async def create_room(
    data: RoomCreate,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin: tạo phòng mới."""
    existing = (await db.execute(select(Room).where(Room.name == data.name))).scalar()
    if existing:
        raise HTTPException(status_code=409, detail="Room with this name already exists")

    room = Room(
        name=data.name,
        building=data.building,
        floor=data.floor,
        capacity=data.capacity,
    )
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return room


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(
    room_id: UUID,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Xem chi tiết phòng + trạng thái sensor realtime."""
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


@router.get("/{room_id}/state")
async def get_room_state(
    room_id: UUID,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Xem trạng thái FSM hiện tại của room."""
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {
        "room_id": str(room_id),
        "name": room.name,
        "mode": room.mode,
        "previous_mode": room.previous_mode,
        "occupancy": room.occupancy,
        "door_locked": room.door_locked,
        "fan_on": room.fan_on,
        "temperature": room.temperature,
        "humidity": room.humidity,
        "co2": room.co2,
    }


@router.put("/{room_id}/state", response_model=RoomResponse)
async def update_room_state(
    room_id: UUID,
    data: RoomStateUpdate,
    _admin: User = Depends(require_role("admin", "lecturer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin/Lecturer: thay đổi FSM state của room.

    FR-FSM-02: Transition state.
    FR-FSM-03: EMERGENCY override tất cả trừ LOCK.
    FR-FSM-04: State persistence — lưu previous_mode.
    """
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # FR-FSM-03: LOCK không bị override bởi EMERGENCY
    if data.mode == "EMERGENCY" and room.mode == "LOCK":
        raise HTTPException(
            status_code=400,
            detail="Cannot override LOCK mode with EMERGENCY (room is locked, no occupants)",
        )

    _MODE_ACTUATORS = {
        "LOCK": (True, False),
        "EMERGENCY": (False, False),
        "EXAM": (True, True),
        "SELF_STUDY": (False, True),
        "LECTURE": (False, True),
        "SAVING": (True, False),
        "SUSPECTED": (False, False),
    }
    target_door_locked, target_fan_on = _MODE_ACTUATORS.get(
        data.mode, (room.door_locked, room.fan_on)
    )
    fan_cmd_val = "on" if target_fan_on else "off"
    door_cmd_val = "locked" if target_door_locked else "unlocked"

    # Validate + execute via Edge FSM first so rejected transitions never mutate DB or publish MQTT.
    await _dispatch_room_command_via_edge(
        room_id,
        "mode",
        data.mode.lower(),
        f"Manual mode update by {_admin.username}",
    )
    await _dispatch_room_command_via_edge(
        room_id,
        "fan",
        fan_cmd_val,
        f"Auto fan sync with mode {data.mode}",
    )

    room.previous_mode = room.mode
    room.mode = data.mode
    room.door_locked = target_door_locked
    room.fan_on = target_fan_on
    await db.commit()
    await db.refresh(room)

    # Broadcast WebSocket tới toàn bộ Digital Twin Web UI
    from app.websocket.manager import ws_manager
    await ws_manager.broadcast({
        "type": "room_mode_changed",
        "room_id": str(room_id),
        "mode": room.mode,
        "previous_mode": room.previous_mode,
        "door_locked": room.door_locked,
        "fan_on": room.fan_on,
    })

    logger.info("Room %s state changed: %s → %s (Fan: %s, Door: %s)", room.name, room.previous_mode, room.mode, fan_cmd_val, door_cmd_val)
    return room


class FanToggleRequest(BaseModel):
    fan_on: bool


class DoorToggleRequest(BaseModel):
    door_locked: bool


@router.post("/{room_id}/fan")
async def toggle_room_fan(
    room_id: UUID,
    payload: FanToggleRequest,
    _user: User = Depends(require_role("admin", "lecturer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin/Lecturer: Bật hoặc tắt quạt của từng phòng học."""
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    target_fan_on = bool(payload.fan_on)
    fan_val = "on" if target_fan_on else "off"
    await _dispatch_room_command_via_edge(
        room_id,
        "fan",
        fan_val,
        f"Manual fan toggle by {_user.username}",
    )

    room.fan_on = target_fan_on
    await db.commit()
    await db.refresh(room)

    # Broadcast WebSocket tới Digital Twin UI
    from app.websocket.manager import ws_manager
    await ws_manager.broadcast({
        "type": "room_telemetry",
        "room_id": str(room_id),
        "data": {
            "room_id": str(room_id),
            "fan_on": room.fan_on,
            "command_type": "fan",
            "command_value": fan_val,
        },
    })

    return {
        "room_id": str(room_id),
        "fan_on": room.fan_on,
        "message": f"Quạt phòng {room.name} đã được {'BẬT' if room.fan_on else 'TẮT'}",
    }


@router.post("/{room_id}/door")
async def toggle_room_door(
    room_id: UUID,
    payload: DoorToggleRequest,
    _user: User = Depends(require_role("admin", "lecturer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin/Lecturer: Mở hoặc khóa cửa của từng phòng học."""
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    target_door_locked = bool(payload.door_locked)
    door_val = "locked" if target_door_locked else "unlocked"
    await _dispatch_room_command_via_edge(
        room_id,
        "door",
        door_val,
        f"Manual door toggle by {_user.username}",
    )

    room.door_locked = target_door_locked
    await db.commit()
    await db.refresh(room)

    # Broadcast WebSocket tới Digital Twin UI
    from app.websocket.manager import ws_manager
    await ws_manager.broadcast({
        "type": "room_telemetry",
        "room_id": str(room_id),
        "data": {
            "room_id": str(room_id),
            "door_locked": room.door_locked,
            "command_type": "door",
            "command_value": door_val,
        },
    })

    return {
        "room_id": str(room_id),
        "door_locked": room.door_locked,
        "message": f"Cửa phòng {room.name} đã được {'KHÓA' if room.door_locked else 'MỞ KHÓA'}",
    }


@router.delete("/{room_id}")
async def delete_room(
    room_id: UUID,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin: xóa phòng."""
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    await db.delete(room)
    await db.commit()
    return {"message": "Room deleted", "room_id": str(room_id)}
