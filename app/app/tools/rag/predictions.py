"""
app/tools/rag/predictions.py
"""

PREDICTIONS_TOOL = {
    "name": "get_predictions",
    "description": "EWMA prediction cho 1 metric trong tương lai gần.",
    "parameters": {
        "room_id": "string",
        "metric": "enum ['temperature', 'co2']",
        "horizon": "enum ['15m', '30m']",
        "required": ["room_id"],
    },
}
