"""
app/tools/actions/alert.py
"""

ALERT_TOOL = {
    "name": "send_alert",
    "description": "Gửi thông báo cảnh báo tới giảng viên hoặc quản trị viên hệ thống.",
    "parameters": {
        "room_id": "string",
        "message": "string",
        "level": "enum ['info', 'warning', 'critical']",
    },
}
