"""
app/campus/hitl.py
------------------
Module quản lý trạng thái Human-in-the-Loop (HITL) và thực thi lệnh công cụ (Tool Execution)
từ AI Recommendation sang Edge Gateway và MQTT Actuators.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any
from uuid import UUID

import httpx
from app.config.settings import settings
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)

# Runtime state cho chế độ HITL
# True  = Bắt buộc người vận hành xác nhận (Manual Approval)
# False = Chế độ Tự động (Auto-pilot / Auto-execute khi tin cậy cao)
_HITL_ENABLED: bool = True


def is_hitl_enabled() -> bool:
    """Kiểm tra chế độ HITL hiện tại."""
    global _HITL_ENABLED
    return _HITL_ENABLED


def set_hitl_enabled(enabled: bool) -> bool:
    """Bật/tắt chế độ HITL."""
    global _HITL_ENABLED
    _HITL_ENABLED = bool(enabled)
    logger.info("Chế độ HITL đã được đổi thành: %s", "BẬT (Manual Confirm)" if _HITL_ENABLED else "TẮT (Auto-pilot)")
    return _HITL_ENABLED


# translate_recommendation_to_command được tách sang module thuần để binding.py dùng chung
# (re-export tại đây để giữ tương thích các import cũ).
from app.campus.command_translation import translate_recommendation_to_command  # noqa: E402,F401


def _edge_commands_base() -> str:
    base_edge_url = settings.BACKEND_BASE_URL.rstrip("/")
    return f"{base_edge_url}/commands" if base_edge_url.endswith("/api") else f"{base_edge_url}/api/commands"


async def fetch_edge_state_snapshot(room_id: UUID | str | None) -> dict[str, Any] | None:
    """Lấy ``{mode, state_version}`` hiện tại của phòng từ Edge (best-effort, timeout ngắn).

    Dùng khi tạo recommendation để bind đề xuất vào đúng trạng thái vật lý mà người duyệt sẽ thấy.
    Trả về ``None`` nếu Edge không phản hồi (khi đó binding chỉ còn payload hash).
    """
    if not room_id:
        return None
    url = f"{_edge_commands_base()}/room/{room_id}/state-snapshot"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.json()
    except Exception as exc:
        logger.warning("Không lấy được state snapshot từ Edge (%s): %s", url, exc)
    return None


async def dispatch_tool_execution(
    rec_id: UUID | str,
    room_id: UUID | str | None,
    tool_name: str,
    tool_params: dict[str, Any],
    reason: str = "",
    operator: str = "operator",
    is_auto: bool = False,
    expected_mode: str | None = None,
    expected_state_version: str | None = None,
) -> dict[str, Any]:
    """Gửi lệnh thực thi sang Edge Gateway API để điều khiển cơ cấu chấp hành vật lý thật."""
    cmd_pair = translate_recommendation_to_command(tool_name, tool_params)
    
    room_id_str = str(room_id) if room_id else ""
    if not room_id_str:
        # Fallback lấy room_id từ tool_params nếu có
        room_id_str = str(tool_params.get("room_id", ""))

    result_summary: dict[str, Any] = {
        "recommendation_id": str(rec_id),
        "tool_name": tool_name,
        "tool_params": tool_params,
        "room_id": room_id_str,
        "operator": operator,
        "is_auto": is_auto,
        "command_executed": False,
        "edge_status": "skipped",
    }

    if not cmd_pair:
        logger.info("Tool %s không cần gửi actuator command xuống phần cứng hoặc bị Fail-Secure từ chối.", tool_name)
        result_summary["edge_status"] = "no_hardware_action_required"
    elif not room_id_str:
        logger.warning("Không có room_id cho tool %s, bỏ qua gọi Edge Gateway.", tool_name)
        result_summary["edge_status"] = "missing_room_id"
    else:
        command_type, command_value = cmd_pair
        result_summary["command_type"] = command_type
        result_summary["command_value"] = command_value

        # TIERED AUTONOMY GATE: Chặn triệt để Autopilot tự ý can thiệp vào cửa hoặc FSM
        if is_auto and command_type in ("door", "mode"):
            logger.warning("🚨 [SAFETY INTERLOCK BLOCKED] Autopilot bị chặn tự động thực thi lệnh nhạy cảm '%s:%s' cho phòng %s!", command_type, command_value, room_id_str)
            result_summary["command_executed"] = False
            result_summary["edge_status"] = "blocked_by_safety_policy"
            result_summary["error_detail"] = "Lệnh can thiệp an ninh cửa/FSM bắt buộc phải có Quản trị viên duyệt qua HITL."
            return result_summary

        # Edge base URL (VD: http://localhost:8000 hoặc cấu hình qua settings)
        base_edge_url = settings.BACKEND_BASE_URL.rstrip("/")
        if not base_edge_url.endswith("/api"):
            execute_url = f"{base_edge_url}/api/commands/room/execute"
        else:
            execute_url = f"{base_edge_url}/commands/room/execute"

        from app.config.safety import toctou_binding_enabled

        toctou_active = toctou_binding_enabled()
        edge_payload = {
            "room_id": room_id_str,
            "command_type": command_type,
            "command_value": command_value,
            "reason": f"AI Recommendation {rec_id} ({'Auto-pilot' if is_auto else 'Approved by ' + operator}): {reason}",
            "source": "ai_agent" if is_auto else "admin_hitl",
            # Physical-TOCTOU binding: Edge sẽ từ chối (409) nếu phòng đã đổi trạng thái sau khi đề xuất.
            "expected_mode": expected_mode if toctou_active else None,
            "expected_state_version": expected_state_version if toctou_active else None,
        }

        edge_accepted = False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                logger.info("Đang gửi lệnh sang Edge Gateway: %s với payload %s", execute_url, edge_payload)
                resp = await client.post(execute_url, json=edge_payload)
                if resp.status_code in (200, 202):
                    edge_accepted = True
                    result_summary["command_executed"] = True
                    result_summary["edge_status"] = "success"
                    result_summary["edge_response"] = resp.json()
                    logger.info("Edge Gateway đã nhận lệnh thành công: %s", resp.text)
                else:
                    result_summary["edge_response"] = resp.text
                    if resp.status_code == 409:
                        result_summary["edge_status"] = "stale_approval"
                    elif resp.status_code == 403:
                        result_summary["edge_status"] = "blocked_by_edge_interlock"
                    else:
                        result_summary["edge_status"] = f"http_error_{resp.status_code}"
                    logger.warning("Edge Gateway từ chối hoặc trả về lỗi: %s - %s", resp.status_code, resp.text)
        except Exception as exc:
            logger.error("Không thể kết nối sang Edge Gateway (%s): %s", execute_url, exc)
            result_summary["edge_status"] = f"connection_failed: {str(exc)}"

        # Phát MQTT dự phòng: CHỈ phát khi Edge Gateway chấp thuận (status 200/202).
        # Tuyệt đối không phát MQTT nếu Edge Gateway đã từ chối (400/403 FSM Barrier)!
        if edge_accepted:
            try:
                from app.websocket.mqtt_bridge import publish_mqtt_message
                import uuid as _uuid
                mqtt_topic = f"smartcampus/v1/command/room/{room_id_str}"
                mqtt_payload = {
                    "message_id": str(_uuid.uuid4()),
                    "source_timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": {
                        "room_id": room_id_str,
                        "command_type": command_type,
                        "command_value": command_value,
                        "reason": edge_payload["reason"],
                        "source": edge_payload["source"],
                    },
                }
                await publish_mqtt_message(mqtt_topic, mqtt_payload)
                logger.info("Đã phát lệnh điều khiển actuator tới MQTT %s: %s", mqtt_topic, mqtt_payload)
            except Exception as mq_err:
                logger.warning("Không thể phát MQTT trực tiếp cho actuator: %s", mq_err)

    # Broadcast sự kiện tới toàn bộ client qua WebSocket
    ws_payload = {
        "type": "recommendation_executed",
        **result_summary,
    }
    await ws_manager.broadcast(ws_payload)

    # Nếu tool là send_alert, phát riêng gói tin system_alert để Frontend mở ngay Pop up cảnh báo
    if tool_name.lower().strip() == "send_alert":
        alert_payload = {
            "type": "system_alert",
            "alert": {
                "id": str(rec_id),
                "recommendation_id": str(rec_id),
                "room_id": room_id_str,
                "tool_name": "send_alert",
                "message": tool_params.get("message") or reason or "Cảnh báo an ninh / an toàn từ AI Agent",
                "level": str(tool_params.get("level", "warning")).lower(),
                "reason": reason,
                "operator": operator,
                "is_auto": is_auto,
                "status": "approved" if not is_auto else "auto_approved",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
        await ws_manager.broadcast(alert_payload)

    return result_summary
