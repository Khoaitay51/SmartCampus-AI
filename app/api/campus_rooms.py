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

    # Lưu previous mode để restore sau EMERGENCY/EXAM
    room.previous_mode = room.mode
    room.mode = data.mode

    # Auto actuator control theo mode (FR-AC-01..03)
    if data.mode == "LOCK":
        room.door_locked = True
        room.fan_on = False
    elif data.mode == "EMERGENCY":
        room.door_locked = False  # FR-AC-02: unlock ngay để thoát hiểm
        room.fan_on = False       # Tắt quạt chống thổi lan khói
    elif data.mode == "EXAM":
        room.door_locked = True   # FR-AC-02: lock chốt trong giờ thi
        room.fan_on = True
    elif data.mode in ("SELF_STUDY", "LECTURE"):
        room.door_locked = False  # Mở cửa cho sinh viên/giảng viên ra vào
        room.fan_on = True        # Bật quạt thông gió vi khí hậu
    elif data.mode == "SAVING":
        room.door_locked = True   # Khóa cửa khi phòng trống
        room.fan_on = False       # Tắt quạt tiết kiệm điện
    elif data.mode == "SUSPECTED":
        room.door_locked = False
        room.fan_on = False

    await db.commit()
    await db.refresh(room)

    # 1. Phát sự kiện WebSocket tới toàn bộ Digital Twin Web UI
    from app.websocket.manager import ws_manager
    await ws_manager.broadcast({
        "type": "room_mode_changed",
        "room_id": str(room_id),
        "mode": room.mode,
        "previous_mode": room.previous_mode,
        "door_locked": room.door_locked,
        "fan_on": room.fan_on,
    })

    # 2. Publish MQTT thông báo cập nhật state & lệnh quạt/cửa trực tiếp xuống ESP32 phần cứng
    from app.websocket.mqtt_bridge import publish_mqtt_message
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    fan_cmd_val = "on" if room.fan_on else "off"
    door_cmd_val = "locked" if room.door_locked else "unlocked"

    # Gửi topic /state
    await publish_mqtt_message(
        f"smartcampus/v1/room/{room_id}/state",
        {
            "room_id": str(room_id),
            "room_mode": room.mode.lower(),
            "room_status": "online",
        },
    )

    # Gửi lệnh quạt trực tiếp qua topic /command/room/{room_id} để ESP32 bật/tắt quạt ngay lập tức
    await publish_mqtt_message(
        f"smartcampus/v1/command/room/{room_id}",
        {
            "message_id": f"sync-fan-{int(datetime.now().timestamp())}",
            "source_timestamp": now_iso,
            "payload": {
                "command_id": f"sync-fan-{room_id}",
                "command_type": "fan",
                "command_value": fan_cmd_val,
                "room_id": str(room_id),
            },
        },
    )

    # 3. Đồng bộ trạng thái sang Edge Gateway & TimescaleDB
    from app.config.settings import settings
    import httpx
    try:
        base_edge_url = settings.BACKEND_BASE_URL.rstrip("/")
        edge_exec_url = f"{base_edge_url}/api/commands/room/execute" if not base_edge_url.endswith("/api") else f"{base_edge_url}/commands/room/execute"
        async with httpx.AsyncClient(timeout=4.0) as client:
            # Sync mode
            await client.post(edge_exec_url, json={
                "room_id": str(room_id),
                "command_type": "mode",
                "command_value": room.mode.lower(),
                "reason": f"Manual mode update by {_admin.username}",
                "source": "dtwin_admin",
            })
            # Sync fan command to Edge
            await client.post(edge_exec_url, json={
                "room_id": str(room_id),
                "command_type": "fan",
                "command_value": fan_cmd_val,
                "reason": f"Auto fan sync with mode {room.mode}",
                "source": "dtwin_admin",
            })
    except Exception as exc:
        logger.warning("Không thể gọi Edge Gateway đồng bộ mode/fan: %s", exc)

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

    room.fan_on = bool(payload.fan_on)
    await db.commit()
    await db.refresh(room)

    fan_val = "on" if room.fan_on else "off"
    from app.websocket.mqtt_bridge import publish_mqtt_message
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Publish MQTT command trực tiếp xuống ESP32
    await publish_mqtt_message(
        f"smartcampus/v1/command/room/{room_id}",
        {
            "message_id": f"fan-{int(datetime.now().timestamp() * 1000)}",
            "source_timestamp": now_iso,
            "payload": {
                "command_id": f"cmd-fan-{room_id}",
                "command_type": "fan",
                "command_value": fan_val,
                "room_id": str(room_id),
            },
        },
    )

    # 2. Đồng bộ Edge Gateway
    from app.config.settings import settings
    import httpx
    try:
        base_edge_url = settings.BACKEND_BASE_URL.rstrip("/")
        edge_exec_url = f"{base_edge_url}/api/commands/room/execute" if not base_edge_url.endswith("/api") else f"{base_edge_url}/commands/room/execute"
        async with httpx.AsyncClient(timeout=4.0) as client:
            await client.post(edge_exec_url, json={
                "room_id": str(room_id),
                "command_type": "fan",
                "command_value": fan_val,
                "reason": f"Manual fan toggle by {_user.username}",
                "source": "dtwin_admin",
            })
    except Exception as exc:
        logger.warning("Không thể gọi Edge Gateway đồng bộ fan: %s", exc)

    # 3. Broadcast WebSocket tới Digital Twin UI
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

    room.door_locked = bool(payload.door_locked)
    await db.commit()
    await db.refresh(room)

    door_val = "locked" if room.door_locked else "unlocked"
    from app.websocket.mqtt_bridge import publish_mqtt_message
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Publish MQTT command trực tiếp xuống ESP32
    await publish_mqtt_message(
        f"smartcampus/v1/command/room/{room_id}",
        {
            "message_id": f"door-{int(datetime.now().timestamp() * 1000)}",
            "source_timestamp": now_iso,
            "payload": {
                "command_id": f"cmd-door-{room_id}",
                "command_type": "door",
                "command_value": door_val,
                "room_id": str(room_id),
            },
        },
    )

    # 2. Đồng bộ Edge Gateway
    from app.config.settings import settings
    import httpx
    try:
        base_edge_url = settings.BACKEND_BASE_URL.rstrip("/")
        edge_exec_url = f"{base_edge_url}/api/commands/room/execute" if not base_edge_url.endswith("/api") else f"{base_edge_url}/commands/room/execute"
        async with httpx.AsyncClient(timeout=4.0) as client:
            await client.post(edge_exec_url, json={
                "room_id": str(room_id),
                "command_type": "door",
                "command_value": door_val,
                "reason": f"Manual door toggle by {_user.username}",
                "source": "dtwin_admin",
            })
    except Exception as exc:
        logger.warning("Không thể gọi Edge Gateway đồng bộ door: %s", exc)

    # 3. Broadcast WebSocket tới Digital Twin UI
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
