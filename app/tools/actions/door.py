"""
app/tools/actions/door.py
"""

DOOR_TOOL = {
    "name": "set_door",
    "description": "Khóa hoặc mở khóa cửa phòng học.",
    "parameters": {"room_id": "string", "state": "enum ['locked', 'unlocked']"},
}
