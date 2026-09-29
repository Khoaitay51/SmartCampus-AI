"""
app/schemas/notable_event.py
---------------------------
Contract & Schemas cho Notable Event (Sự kiện đáng chú ý).
Topic MQTT: smartcampus/v1/event/room/{room_id}/notable

Được Edge Gateway (SmartCampus-edge) publish khi phát hiện các biến cố đáng chú ý:
- Khói bất thường / nghi ngờ cháy (smoke_detected / smoke_suspected / smoke_emergency)
- Nhiệt độ / độ ẩm tăng đột biến (temperature_anomaly)
- Nồng độ CO2 vượt ngưỡng an toàn (co2_hazard)
- Chênh lệch sĩ số giữa cảm biến IR và danh sách điểm danh RFID (occupancy_discrepancy)
- Quẹt thẻ RFID lạ chưa đăng ký tại phòng học (rfid_unknown)
- Lãng phí năng lượng (energy_waste: phòng bật điều hòa/quạt nhưng không có người)
- Chuyển trạng thái khẩn cấp FSM (fsm_override)
- Thao tác thủ công từ người quản trị / DTwin (manual_trigger)

AI Service subscribe topic này (smartcampus/v1/event/room/+/notable) để nhận tín hiệu,
lưu trữ, chuyển tiếp lên Digital Twin UI qua WebSocket, và sẵn sàng kích hoạt AI Agent.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class NotableEventType(str, Enum):
    SMOKE_DETECTED = "smoke_detected"
    TEMPERATURE_ANOMALY = "temperature_anomaly"
    CO2_HAZARD = "co2_hazard"
    OCCUPANCY_DISCREPANCY = "occupancy_discrepancy"
    RFID_UNKNOWN = "rfid_unknown"
    ENERGY_WASTE = "energy_waste"
    FSM_OVERRIDE = "fsm_override"
    MANUAL_TRIGGER = "manual_trigger"


class NotableEventSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class NotableEventPayload(BaseModel):
    event_id: UUID = Field(default_factory=uuid4, description="Unique ID của event")
    event_type: NotableEventType = Field(..., description="Loại sự kiện đáng chú ý")
    severity: NotableEventSeverity = Field(default=NotableEventSeverity.WARNING, description="Mức độ nghiêm trọng")
    room_id: UUID = Field(..., description="ID của phòng xảy ra sự kiện")
    room_name: Optional[str] = Field(default=None, description="Tên phòng (nếu có)")
    title: str = Field(..., description="Tiêu đề tóm tắt sự kiện")
    description: str = Field(..., description="Mô tả chi tiết nguyên nhân / cảnh báo")
    event_data: dict[str, Any] = Field(default_factory=dict, description="Dữ liệu cảm biến/ngữ cảnh chi tiết")
    requires_agent: bool = Field(default=True, description="Cờ đánh dấu sự kiện cần AI Agent xem xét")


class NotableEventEnvelope(BaseModel):
    """Envelope chuẩn theo format của SmartCampus Edge MQTT."""
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    source_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: NotableEventPayload
