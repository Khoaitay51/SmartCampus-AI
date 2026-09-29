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

    # Auto actuator control theo mode
    if data.mode == "LOCK":
        room.door_locked = True
        room.fan_on = False
    elif data.mode == "EMERGENCY":
        room.door_locked = False  # FR-AC-02: unlock ngay
    elif data.mode == "EXAM":
        room.door_locked = True   # FR-AC-02: lock trong exam

    await db.commit()
    await db.refresh(room)

    logger.info("Room %s state changed: %s → %s", room.name, room.previous_mode, room.mode)
    return room


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
