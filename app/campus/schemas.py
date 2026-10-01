"""
app/campus/schemas.py
---------------------
Pydantic schemas cho Room, Device, Session, Attendance, Recommendation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Room Schemas
# ---------------------------------------------------------------------------

class RoomCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    building: Optional[str] = None
    floor: Optional[int] = None
    capacity: int = 40


class RoomResponse(BaseModel):
    id: UUID
    name: str
    building: Optional[str] = None
    floor: Optional[int] = None
    capacity: Optional[int] = None
    mode: str
    previous_mode: Optional[str] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    co2: Optional[float] = None
    occupancy: int
    door_locked: bool
    fan_on: bool

    model_config = {"from_attributes": True}


class RoomStateUpdate(BaseModel):
    """Admin/system update room FSM state."""
    mode: str = Field(..., description="New FSM mode")

    def model_post_init(self, __context: Any) -> None:
        valid = {"SAVING", "SELF_STUDY", "LECTURE", "EXAM", "LOCK", "SUSPECTED", "EMERGENCY"}
        if self.mode not in valid:
            raise ValueError(f"mode must be one of {valid}")


# ---------------------------------------------------------------------------
# Device Schemas
# ---------------------------------------------------------------------------

class DeviceCreate(BaseModel):
    mac_address: str = Field(..., min_length=8, max_length=20)
    name: Optional[str] = None
    device_type: str = "sensor_node"


class DeviceResponse(BaseModel):
    id: UUID
    mac_address: str
    name: Optional[str] = None
    device_type: Optional[str] = None
    firmware_version: Optional[str] = None
    room_id: Optional[UUID] = None
    status: str
    last_heartbeat: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DeviceAssign(BaseModel):
    room_id: UUID


# ---------------------------------------------------------------------------
# Session & Attendance Schemas
# ---------------------------------------------------------------------------

class SessionCreate(BaseModel):
    room_id: UUID
    mode: str = "LECTURE"


class SessionResponse(BaseModel):
    id: UUID
    room_id: UUID
    lecturer_id: Optional[UUID] = None
    mode: str
    started_at: datetime
    checkin_deadline: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    is_active: bool

    model_config = {"from_attributes": True}


class AttendanceResponse(BaseModel):
    id: UUID
    session_id: UUID
    student_id: UUID
    rfid_uid: Optional[str] = None
    checked_in_at: datetime
    is_late: bool
    status: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# AI Recommendation (HITL) Schemas
# ---------------------------------------------------------------------------

class RecommendationResponse(BaseModel):
    id: UUID
    event_id: Optional[str] = None
    room_id: Optional[UUID] = None
    tool_name: str
    tool_params: dict[str, Any] = Field(default_factory=dict)
    reason: Optional[str] = None
    confidence: Optional[float] = None
    urgency: Optional[str] = None
    status: str
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime
    execution_result: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}


class RecommendationAction(BaseModel):
    """HITL approve/reject action."""
    action: str = Field(..., description="'approve' or 'reject'")
    notes: Optional[str] = None


class HitlToggleRequest(BaseModel):
    """Request model cho endpoint toggle HITL."""
    enabled: Optional[bool] = None
