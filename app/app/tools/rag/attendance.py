"""
app/tools/rag/attendance.py
"""

ATTENDANCE_TOOL = {
    "name": "get_attendance",
    "description": "Query attendance records theo phòng/session/lớp.",
    "parameters": {
        "room_id": "string",
        "session_id": "string",
        "class_code": "string",
    },
}
