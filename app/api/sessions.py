"""
app/api/sessions.py
-------------------
Session & Attendance management router.
FR-SA-01..05.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user, require_role
from app.auth.models import User
from app.campus.models import AttendanceRecord, Room, RoomSession
from app.campus.schemas import AttendanceResponse, SessionCreate, SessionResponse
from app.database.session import get_async_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["Sessions & Attendance"])


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    room_id: UUID | None = None,
    active_only: bool = False,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Liệt kê sessions, filter theo room hoặc active status."""
    query = select(RoomSession)
    if room_id:
        query = query.where(RoomSession.room_id == room_id)
    if active_only:
        query = query.where(RoomSession.is_active == True)

    result = await db.execute(query.order_by(RoomSession.started_at.desc()).limit(100))
    return result.scalars().all()


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    data: SessionCreate,
    current_user: User = Depends(require_role("admin", "lecturer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Lecturer/Admin: tạo session mới (FR-SA-01).

    GV quét RFID → tạo session với started_at = NOW().
    Checkin window = started_at + 15 phút.
    """
    room = await db.get(Room, data.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Check existing active session
    existing = (await db.execute(
        select(RoomSession).where(
            and_(RoomSession.room_id == data.room_id, RoomSession.is_active == True)
        )
    )).scalar()
    if existing:
        raise HTTPException(status_code=409, detail="Room already has an active session")

    now = datetime.now(timezone.utc)
    session = RoomSession(
        room_id=data.room_id,
        lecturer_id=current_user.id if current_user.role == "lecturer" else None,
        mode=data.mode,
        started_at=now,
        checkin_deadline=now + timedelta(minutes=15),
        is_active=True,
    )
    db.add(session)

    # Update room mode
    room.previous_mode = room.mode
    room.mode = data.mode
    await db.commit()
    await db.refresh(session)

    logger.info("Session created for room %s by %s", room.name, current_user.username)
    return session


@router.post("/{session_id}/close", response_model=SessionResponse)
async def close_session(
    session_id: UUID,
    _user: User = Depends(require_role("admin", "lecturer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Lecturer/Admin: đóng session (FR-SA-02)."""
    session = await db.get(RoomSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.is_active:
        raise HTTPException(status_code=400, detail="Session already closed")

    session.ended_at = datetime.now(timezone.utc)
    session.is_active = False

    # Restore room mode
    room = await db.get(Room, session.room_id)
    if room and room.mode in ("LECTURE", "EXAM"):
        room.mode = room.previous_mode or "SELF_STUDY" if room.occupancy > 0 else "SAVING"

    await db.commit()
    await db.refresh(session)
    return session


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------

@router.get("/{session_id}/attendance", response_model=list[AttendanceResponse])
async def get_session_attendance(
    session_id: UUID,
    _user: User = Depends(require_role("admin", "lecturer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Lecturer/Admin: xem attendance records cho 1 session."""
    result = await db.execute(
        select(AttendanceRecord)
        .where(AttendanceRecord.session_id == session_id)
        .order_by(AttendanceRecord.checked_in_at)
    )
    return result.scalars().all()


@router.post("/{session_id}/checkin")
async def student_checkin(
    session_id: UUID,
    rfid_uid: str = Query(..., description="RFID UID của student"),
    db: AsyncSession = Depends(get_async_db),
):
    """Internal: student check-in vào session (FR-RF-03, FR-SA-01).

    Được gọi từ MQTT bridge khi SV quét RFID tại cửa phòng.
    """
    from app.auth.models import RFIDCard

    session = await db.get(RoomSession, session_id)
    if not session or not session.is_active:
        raise HTTPException(status_code=400, detail="No active session")

    # Lookup RFID
    card = (await db.execute(select(RFIDCard).where(RFIDCard.uid == rfid_uid))).scalar()
    if not card or not card.is_registered or not card.user_id:
        return {"status": "rejected", "reason": "Card not registered"}

    user = await db.get(User, card.user_id)
    if not user or user.role != "student":
        return {"status": "rejected", "reason": "Not a student card"}

    # Check duplicate
    existing = (await db.execute(
        select(AttendanceRecord).where(
            and_(
                AttendanceRecord.session_id == session_id,
                AttendanceRecord.student_id == user.id,
            )
        )
    )).scalar()
    if existing:
        return {"status": "already_checked_in", "student": user.username}

    now = datetime.now(timezone.utc)
    is_late = session.checkin_deadline and now > session.checkin_deadline

    record = AttendanceRecord(
        session_id=session_id,
        student_id=user.id,
        rfid_uid=rfid_uid,
        checked_in_at=now,
        is_late=is_late,
        status="late" if is_late else "present",
    )
    db.add(record)
    await db.commit()

    return {
        "status": "success",
        "student": user.username,
        "full_name": user.full_name,
        "is_late": is_late,
        "checked_in_at": now.isoformat(),
    }
