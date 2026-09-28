import json
from copy import deepcopy
from datetime import datetime, timezone

files = [
    r'tests/fixtures/test_cases_rag_challenging_1_4.json',
    r'tests/fixtures/test_cases_rag_challenging_5_10.json',
    r'tests/fixtures/test_cases_rag_challenging.json'
]

empty_telemetry = {
  "window_start": "2026-09-24T00:00:00Z",
  "window_end": "2026-09-24T00:00:00Z",
  "temperature": {"min": 0, "max": 0, "avg": 0, "latest": 0},
  "humidity": {"min": 0, "max": 0, "avg": 0, "latest": 0},
  "co2": {"min": 0, "max": 0, "avg": 0, "latest": 0},
  "smoke_value": {"min": 0, "max": 0, "avg": 0, "latest": 0},
  "air_quality": {"min": 0, "max": 0, "avg": 0, "latest": 0}
}

empty_occupancy = {
  "current_count": 0,
  "total_in": 0,
  "total_out": 0,
  "trend": "stable"
}

for fpath in files:
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    scenarios = data.get('scenarios', [])
    for sc in scenarios:
        context = sc['payload']['operational_context']
        
        # Build mock_tool_responses based on the rich data
        mock_responses = {
            "get_telemetry": {"room_id": context['room']['room_id'], "data": context.get('telemetry_summary', empty_telemetry)},
            "get_schedule": {"room_id": context['room']['room_id'], "active_session": context.get('active_session')},
            "get_occupancy": {"room_id": context['room']['room_id'], "data": context.get('occupancy', empty_occupancy)},
            "get_room_history": {"room_id": context['room']['room_id'], "events": context.get('recent_events', [])}
        }
        
        sc['mock_tool_responses'] = mock_responses
        
        # Strip context to make LLM hungry for data
        context['telemetry_summary'] = empty_telemetry
        context['occupancy'] = empty_occupancy
        context['active_session'] = None
        context['recent_events'] = []
    
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

print("Transformed all files successfully.")
