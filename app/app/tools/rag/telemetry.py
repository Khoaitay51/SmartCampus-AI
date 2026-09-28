"""
app/tools/rag/telemetry.py
"""

TELEMETRY_TOOL = {
    "name": "get_telemetry",
    "description": "Query raw time-series data cho 1 metric cụ thể của 1 phòng.",
    "parameters": {
        "room_id": "string",
        "metric": "enum ['temperature', 'humidity', 'co2', 'smoke', 'occupancy']",
        "window": "enum ['15m', '1h', '6h']",
        "required": ["room_id"]
    },
}
