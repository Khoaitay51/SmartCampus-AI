from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

from app.schemas.events import EventPayload
from app.schemas.events import EventType
from app.schemas.recommendation import ToolRecommendation
from app.schemas.recommendation import ALLOWED_ACTION_TOOLS

def validate_event(event_name: str, params: str) -> None:
    if not EventType:
        raise ValueError("New event is required")

    if event_name == "smoke_detected":
        if "room_id" not in params:
            raise ValueError("Room ID is required")

    if event_name == "occupancy_change":
        if "room_id" not in params:
            raise ValueError("Room ID is required")

    if event_name == "temperature_anomaly":
        if "room_id" not in params:
            raise ValueError("Room ID is required")

    if event_name == "rfid_unknown":
        if "room_id" not in params:
            raise ValueError("Room ID is required")

    if event_name == "manual_trigger":
        if "room_id" not in params:
            raise ValueError("Room ID is required")
    

ALLOWED_STATE_FAN = {"on", "off"}
ALLOWED_STATE_DOOR = {"locked", "unlocked"}
ALLOWED_STATE_LIGHT = {"on", "off"}
ALLOWED_STATE_RMODE = {"saving", "self_study", "lecture", "exam", "lock", "suspected", "emergency"}
ALLOWED_STATE_LED = {"static", "breathe", "solid", "blink", "off"}
ALLOWED_STATE_BUZZER = {"on", "off", "short", "long", "continuous", "emergency"}
def validate_tool_call(tool_name: str, params: str) -> None:
    if not ALLOWED_ACTION_TOOLS:
        raise ValueError("Tool name is required")

    if tool_name == "fan_control":
        if "room_id" not in params:
            raise ValueError("Room ID is required")
        if params.get("state") not in ALLOWED_STATE_FAN:
            raise ValueError("Invalid fan state")

    if tool_name == "door_control":
        if "room_id" not in params:
            raise ValueError("Room ID is required")
        if params.get("state") not in ALLOWED_STATE_DOOR:
            raise ValueError("Invalid door state")

    if tool_name == "mode_control": 
        if "room_id" not in params:
            raise ValueError("Room ID is required")
        if params.get("state") not in ALLOWED_STATE_RMODE:
            raise ValueError("Invalid door state")

    if tool_name == "led_strip_control":
        if "room_id" not in params:
            raise ValueError("Room ID is required")
        if params.get("state") not in ALLOWED_STATE_LED:
            raise ValueError("Invalid door state")

    if tool_name == "light_control":
        if "room_id" not in params:
            raise ValueError("Room ID is required")
        if params.get("state") not in ALLOWED_STATE_LIGHT:
            raise ValueError("Invalid door state")

    if tool_name == "buzzer_control":
        if "room_id" not in params:
            raise ValueError("Room ID is required")
        if params.get("state") not in ALLOWED_STATE_BUZZER:
            raise ValueError("Invalid door state")