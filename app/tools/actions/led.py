"""
app/tools/actions/led.py
"""

LED_TOOL = {
    "name": "set_led",
    "description": "Điều khiển đèn LED hiển thị trạng thái phòng.",
    "parameters": {"room_id": "string", "state": "enum ['solid', 'blink']"},
}
