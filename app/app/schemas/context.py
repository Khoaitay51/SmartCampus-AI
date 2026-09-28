from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field

class SensorsStats(BaseModel):
    min: float
    max: float
    avg: float
    latest: float

class RoomInfo(BaseModel):
    room_id: UUID
    room_name: str
    room_type: str
    current_mode: str  
    smoke_state: str

class TelemetrySummary(BaseModel):
    window_start: datetime
    window_end: datetime
    temperature: SensorsStats
    humidity: SensorsStats
    co2: SensorsStats
    smoke_value: SensorsStats
    air_quality: SensorsStats


class Occupancy(BaseModel):
    current_count: int
    total_in: int
    total_out: int
    trend: str # Phong hoc | phong thi


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
    extra: dict[str, Any] = Field(default_factory=dict)


class EnvironmentReading(BaseModel):
    environment_id: int | None = None
    room_id: UUID
    temperature: float | None = None
    humidity: float | None = None
    smoke_detected: bool | None = None
    smoke_value: float | None = None
    smoke_threshold: float | None = None
    smoke_state: str | None = None
    co2: int | None = None
    air_quality: int | None = None
    room_mode: str | None = None
    message_id: str | None = None
    source_timestamp: datetime | None = None
    gateway_received_timestamp: datetime | None = None
    environment_timestamp: datetime


class EnvironmentContext(BaseModel):
    source: str = "edge.query_tool.get_environment"
    since: datetime
    row_count: int
    readings: list[EnvironmentReading] = Field(default_factory=list)


class OperationalContext(BaseModel):
    room: RoomInfo
    telemetry_summary: TelemetrySummary
    occupancy: Occupancy
    active_session: ActiveSession | None = None
    recent_events: list[dict[str, Any]] = Field(default_factory=list)
    environment_context: EnvironmentContext | None = None
