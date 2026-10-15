from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import AliasChoices, BaseModel, Field

class SensorsStats(BaseModel):
    min: float | None = None
    max: float | None = None
    avg: float | None = None
    latest: float | None = None

class RoomInfo(BaseModel):
    room_id: UUID
    room_name: str = "Default Room"
    room_type: str = "generic"
    current_mode: str = "NORMAL"
    smoke_state: str = "CLEAR"

class TelemetrySummary(BaseModel):
    window_start: datetime | None = None
    window_end: datetime | None = None
    temperature: SensorsStats = Field(default_factory=SensorsStats)
    humidity: SensorsStats = Field(default_factory=SensorsStats)
    co2: SensorsStats = Field(default_factory=SensorsStats)
    smoke_value: SensorsStats = Field(default_factory=SensorsStats)
    air_quality: SensorsStats = Field(default_factory=SensorsStats)


class Occupancy(BaseModel):
    current_count: int = 0
    total_in: int = 0
    total_out: int = 0
    trend: str = "on_dinh"


class ActiveSession(BaseModel):
    session_id: UUID
    lecturer_name: str = ""
    class_code: str = ""
    started_at: datetime | None = None
    attendance_deadline: datetime | None = None
    is_exam: bool = False
    checked_in_count: int = 0
    enrolled_count: int = 0


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
    environment_timestamp: datetime | None = None


class EnvironmentContext(BaseModel):
    source: str = "edge.query_tool.get_environment"
    since: datetime | None = None
    row_count: int = 0
    readings: list[EnvironmentReading] = Field(default_factory=list)


class OperationalContext(BaseModel, extra="allow"):
    room: RoomInfo = Field(default_factory=lambda: RoomInfo(room_id=UUID("00000000-0000-0000-0000-000000000000")), validation_alias=AliasChoices("room", "room_info"))
    telemetry_summary: TelemetrySummary = Field(default_factory=TelemetrySummary)
    occupancy: Occupancy = Field(default_factory=Occupancy)
    active_session: ActiveSession | None = None
    recent_events: list[dict[str, Any]] = Field(default_factory=list)
    environment_context: EnvironmentContext | None = None

