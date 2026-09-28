"""
app/safety/policy.py
--------------------
Quy tắc kiểm tra an toàn hệ thống (Safety Policy Engine).
"""
from __future__ import annotations

import logging
from typing import Any

from app.safety.permissions import is_allowed
from app.schemas.events import EventPayload
from app.schemas.recommendation import AgentResponse

logger = logging.getLogger("app.safety.policy")


class SafetyPolicyEngine:
    """Đánh giá tuân thủ quy định an toàn đối với khuyến nghị điều khiển thiết bị."""

    @staticmethod
    def validate_response(event: EventPayload, response: AgentResponse) -> bool:
        if response.skip or response.recommendation is None:
            return True

        tool_name = response.recommendation.tool
        event_type_str = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)

        if not is_allowed(event_type_str, tool_name):
            logger.warning("Policy violation: Tool `%s` không nằm trong danh sách được phép của event `%s`", tool_name, event_type_str)
            return False

        return True
