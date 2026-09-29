"""
app/api/devices.py
------------------
Device management router — CRUD + room assignment.
(Phần device auto-provisioning đã được loại bỏ do Edge và ESP32 quản lý trực tiếp qua MQTT).
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user, require_role
from app.auth.models import User
from app.campus.models import Device, Room
from app.campus.schemas import DeviceAssign, DeviceCreate, DeviceResponse
from app.database.session import get_async_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["Devices"])


@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    status: str | None = None,
    room_id: UUID | None = None,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Liệt kê tất cả devices, filter theo status hoặc room."""
    query = select(Device)
    if status:
        query = query.where(Device.status == status)
    if room_id:
        query = query.where(Device.room_id == room_id)

    result = await db.execute(query.order_by(Device.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=DeviceResponse, status_code=201)
async def register_device(
    data: DeviceCreate,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin: đăng ký device mới thủ công."""
    existing = (await db.execute(select(Device).where(Device.mac_address == data.mac_address))).scalar()
    if existing:
        raise HTTPException(status_code=409, detail="Device with this MAC address already registered")

    device = Device(
        mac_address=data.mac_address,
        name=data.name,
        device_type=data.device_type,
        status="offline",
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Xem chi tiết device."""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.post("/{device_id}/assign", response_model=DeviceResponse)
async def assign_device_to_room(
    device_id: UUID,
    data: DeviceAssign,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin: assign device vào room (FR-DM-02).

    Mapping MAC → room_id lưu vào database. Frontend DTwin gửi lệnh này.
    """
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    room = await db.get(Room, data.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    device.room_id = data.room_id
    device.status = "online"
    await db.commit()
    await db.refresh(device)

    logger.info("Device %s assigned to room %s", device.mac_address, room.name)
    return device


@router.delete("/{device_id}")
async def delete_device(
    device_id: UUID,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin: xóa device."""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    await db.delete(device)
    await db.commit()
    return {"message": "Device deleted", "device_id": str(device_id)}
