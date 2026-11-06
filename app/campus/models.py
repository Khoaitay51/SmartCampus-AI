"""
app/campus/models.py
--------------------
SQLAlchemy models cho Room, Device, RoomSession, AttendanceRecord.
Hỗ trợ FSM 7 states, device provisioning, session/attendance tracking.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.models import Base


# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------

class Room(Base):
    """Phòng học / phòng lab trong campus."""
    __tablename__ = "rooms"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('SAVING','SELF_STUDY','LECTURE','EXAM','LOCK','SUSPECTED','EMERGENCY')",
            name="check_room_mode",
        ),
        {"schema": "campus"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    building = Column(String(100), nullable=True)
    floor = Column(Integer, nullable=True)
    capacity = Column(Integer, nullable=True, default=40)

    # FSM state (FR-FSM-01)
    mode = Column(String(20), nullable=False, default="SAVING")
    previous_mode = Column(String(20), nullable=True)

    # Realtime sensor data cache
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    co2 = Column(Float, nullable=True)
    occupancy = Column(Integer, nullable=False, default=0)

    # Actuator states
    door_locked = Column(Boolean, nullable=False, default=True)
    fan_on = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    devices = relationship("Device", back_populates="room")
    sessions = relationship("RoomSession", back_populates="room")


# ---------------------------------------------------------------------------
# Device (ESP32 nodes)
# ---------------------------------------------------------------------------

class Device(Base):
    """ESP32 node trong hệ thống SmartCampus."""
    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('online','offline','provisioning')",
            name="check_device_status",
        ),
        {"schema": "campus"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mac_address = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    device_type = Column(String(50), nullable=True, default="sensor_node")
    firmware_version = Column(String(50), nullable=True)
    room_id = Column(UUID(as_uuid=True), ForeignKey("campus.rooms.id"), nullable=True)

    status = Column(String(20), nullable=False, default="offline")
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)
    ip_address = Column(String(50), nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True, default=dict)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    room = relationship("Room", back_populates="devices")


# ---------------------------------------------------------------------------
# Room Session & Attendance (FR-SA-01..05)
# ---------------------------------------------------------------------------

class RoomSession(Base):
    """Session phòng học — tạo khi GV quét RFID, đóng khi GV quét ra hoặc timeout."""
    __tablename__ = "room_sessions"
    __table_args__ = {"schema": "campus"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(UUID(as_uuid=True), ForeignKey("campus.rooms.id"), nullable=False, index=True)
    lecturer_id = Column(UUID(as_uuid=True), ForeignKey("campus.users.id"), nullable=True)
    mode = Column(String(20), nullable=False, default="LECTURE")
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    checkin_deadline = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    room = relationship("Room", back_populates="sessions")
    attendances = relationship("AttendanceRecord", back_populates="session")


class AttendanceRecord(Base):
    """Bản ghi điểm danh SV trong session."""
    __tablename__ = "attendance_records"
    __table_args__ = {"schema": "campus"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("campus.room_sessions.id"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("campus.users.id"), nullable=False)
    rfid_uid = Column(String(50), nullable=True)
    checked_in_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_late = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default="present")  # present, late, rejected

    # Relationships
    session = relationship("RoomSession", back_populates="attendances")


# ---------------------------------------------------------------------------
# AI Recommendation (HITL)
# ---------------------------------------------------------------------------

class AIRecommendation(Base):
    """AI agent recommendation chờ HITL approve/reject (FR-AI-05)."""
    __tablename__ = "ai_recommendations"
    __table_args__ = {"schema": "campus"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String, nullable=True, index=True)
    room_id = Column(UUID(as_uuid=True), ForeignKey("campus.rooms.id"), nullable=True)
    tool_name = Column(String(100), nullable=False)
    tool_params = Column(JSON, nullable=False, default=dict)
    reason = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    urgency = Column(String(20), nullable=True, default="medium")

    # HITL status
    status = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("campus.users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
