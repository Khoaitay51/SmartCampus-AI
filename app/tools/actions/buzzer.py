"""
app/tools/actions/buzzer.py
"""

BUZZER_TOOL = {
    "name": "trigger_buzzer",
    "description": "Kích hoạt còi báo động trong phòng học.",
    "parameters": {"room_id": "string", "pattern": "enum ['short', 'long', 'continuous']"},
}
