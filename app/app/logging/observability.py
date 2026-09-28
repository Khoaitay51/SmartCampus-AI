"""
app/logging/observability.py
-----------------------------
Hệ thống quan sát (Observability), cấu hình structured JSON logging và metrics tracing.
"""
from __future__ import annotations

import logging
import sys
from typing import Any


def setup_observability(log_level: str = "INFO") -> None:
    """Cấu hình root logger với định dạng chuẩn cho AI Agent."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def log_agent_trace(event_id: str, step_name: str, details: dict[str, Any]) -> None:
    logger = logging.getLogger("app.observability")
    logger.info("[TRACE] event_id=%s step=%s details=%s", event_id, step_name, details)
