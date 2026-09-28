"""
app/tools/rag/search_history.py
"""
from dataclasses import dataclass, field
from typing import Any

SEARCH_HISTORY_TOOL = {
    "name": "search_history",
    "description": "Semantic search qua pgvector embeddings trên telemetry summaries lịch sử.",
    "parameters": {
        "query": "string",
        "room_id": "string",
        "time_range": "enum ['1h', '6h', '24h', '7d']",
    },
}
