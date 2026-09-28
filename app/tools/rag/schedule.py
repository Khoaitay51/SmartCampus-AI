"""
app/tools/rag/schedule.py
"""

SCHEDULE_TOOL = {
    "name": "get_schedule",
    "description": "Query lịch học theo phòng hoặc theo ngày.",
    "parameters": {
        "room_id": "string",
        "date": "string (YYYY-MM-DD)",
        "required": ["room_id"]
    },
}
