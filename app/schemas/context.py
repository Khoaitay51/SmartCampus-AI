from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RoomInfo(BaseModel):
    room_id: UUID
    room_name: str
    room_type: str
    current_mode: str  
    smoke_state: str


class SensorsStats(BaseModel):
    min: float
    max: float
    avg: float
    latest: float


class TelemetrySummary(BaseModel):
    window_start: datetime
    window_end: datetime
    temperature: SensorsStats
    humidity: SensorsStats
    co2: SensorsStats
    smoke_value: SensorsStats


class Occupancy(BaseModel):
    current_count: int
    total_in: int
    total_out: int
    trend: str


class ActiveSession(BaseModel):
    session_id: UUID
    lecturer_name: str
    class_code: str
    started_at: datetime
    attendance_deadline: datetime
    is_exam: bool
    checked_in_count: int
    enrolled_count: int


class RecentEvent(BaseModel):
    type: str
    time: datetime    
    extra: dict = {}


class OperationalContext(BaseModel):
    room: RoomInfo
    telemetry_summary: TelemetrySummary
    occupancy: Occupancy
    active_session: ActiveSession | None = None
    recent_events: list[dict] = []