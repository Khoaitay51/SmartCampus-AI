
ALLOWED_TOOLS = {
    "temperature_anomaly": {
        "search_history",
        "get_telemetry",
        "set_fan",
        "set_alert",
    },
    "smoke_detected": {
        "search_history",
        "get_telemetry",
        "trigger_buzzer",
        "set_alert",
        "set_led",
    },
    "occupancy_change": {
        "get_room_history",
        "set_door",
        "set_alert",

    },
    "rfid_unknown": {
        "get_attendance",
        "set_alert",
    }, 
    "manual_trigger": {
        "search_history",
    },
}

def is_allowed(event_type: str, tool_name: str) -> bool:
    return tool_name in ALLOWED_TOOLS.get(event_type, set())