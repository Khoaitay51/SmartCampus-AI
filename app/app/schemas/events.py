from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EventType(str, Enum):
    SMOKE_DETECTED = "smoke_detected"
    OCCUPANCY_CHANGE = "occupancy_change"
    TEMPERATURE_ANOMALY = "temperature_anomaly"
    RFID_UNKNOWN = "rfid_unknown"
    MANUAL_TRIGGER = "manual_trigger"


class EventPayload(BaseModel):
    event_id: UUID
    event_type: EventType
    room_id: UUID
    timestamp: datetime
    event_data: dict[str, Any] = Field(default_factory=dict)
    operational_context: dict[str, Any] = Field(default_factory=dict)