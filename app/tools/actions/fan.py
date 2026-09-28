"""
app/tools/actions/fan.py
"""

FAN_TOOL = {
    "name": "set_fan",
    "description": "Bật hoặc tắt quạt thông gió/làm mát trong phòng.",
    "parameters": {"room_id": "string", "state": "enum ['on', 'off']"},
}
