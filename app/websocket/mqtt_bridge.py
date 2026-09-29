"""
app/websocket/mqtt_bridge.py
----------------------------
MQTT → WebSocket bridge — subscribe tất cả campus MQTT topics từ SmartCampus-edge,
forward messages tới WebSocket clients realtime.

FR-DT-07: Latency < 200ms từ ESP32/Edge đến DTwin update.

Topics subscribed (chuẩn theo namespace smartcampus/v1 của SmartCampus-edge):
- smartcampus/v1/telemetry/room/+/environment  → Sensor telemetry (temp, hum, co2, smoke)
- smartcampus/v1/telemetry/room/+/occupancy    → Dual IR occupancy counter
- smartcampus/v1/room/+/state                  → FSM room mode & status (retain)
- smartcampus/v1/room/+/discrepancy            → So lệch occupancy vs attendance
- smartcampus/v1/event/room/+/rfid             → RFID scan events
- smartcampus/v1/event/room/+/notable          → SỰ KIỆN ĐÁNG CHÚ Ý từ Edge (kêu gọi Agent)
- smartcampus/v1/device/+/heartbeat            → ESP32 heartbeat (30s)
- smartcampus/v1/device/+/status               → Device online/offline / LWT (retain)
- smartcampus/v1/command/room/+                → Actuator command (door, fan, buzzer, led)
- smartcampus/v1/ack/device/+/command/+        → Command execution ACK từ thiết bị
- smartcampus/v1/ai/recommendation             → AI tool recommendations (HITL)
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.config.settings import settings
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)

# Topics synced với SmartCampus-edge namespace "smartcampus/v1"
MQTT_TOPICS = [
    # Telemetry
    "smartcampus/v1/telemetry/room/+/environment",
    "smartcampus/v1/telemetry/room/+/occupancy",
    # Room FSM state & discrepancy
    "smartcampus/v1/room/+/state",
    "smartcampus/v1/room/+/discrepancy",
    # Events
    "smartcampus/v1/event/room/+/rfid",
    "smartcampus/v1/event/room/+/notable",
    # Devices
    "smartcampus/v1/device/+/heartbeat",
    "smartcampus/v1/device/+/status",
    # Commands & Acks
    "smartcampus/v1/command/room/+",
    "smartcampus/v1/ack/device/+/command/+",
    # AI recommendations
    "smartcampus/v1/ai/recommendation",
]


def _parse_room_id_from_topic(topic: str) -> str | None:
    """Extract room_id từ topic có pattern .../room/{room_id}/..."""
    parts = topic.split("/")
    if "room" in parts:
        idx = parts.index("room")
        if idx + 1 < len(parts) and parts[idx + 1] != "+":
            return parts[idx + 1]
    return None


def _parse_device_mac_from_topic(topic: str) -> str | None:
    """Extract device MAC hoặc ID từ topic có pattern .../device/{mac}/..."""
    parts = topic.split("/")
    if "device" in parts:
        idx = parts.index("device")
        if idx + 1 < len(parts) and parts[idx + 1] != "+":
            return parts[idx + 1]
    return None


async def _handle_mqtt_message(topic: str, raw_payload: dict[str, Any]) -> None:
    """Route MQTT message tới WebSocket clients dựa trên topic type và room/device filter."""
    room_id = _parse_room_id_from_topic(topic)
    device_id = _parse_device_mac_from_topic(topic)

    # Edge chuẩn hóa envelope: {"message_id": "...", "source_timestamp": "...", "payload": {...}}
    inner = raw_payload.get("payload", raw_payload) if isinstance(raw_payload, dict) else raw_payload

    ws_message: dict[str, Any] = {
        "source": "mqtt",
        "topic": topic,
        "data": inner,
    }
    if isinstance(raw_payload, dict) and "message_id" in raw_payload:
        ws_message["message_id"] = raw_payload.get("message_id")
    if isinstance(raw_payload, dict) and "source_timestamp" in raw_payload:
        ws_message["timestamp"] = raw_payload.get("source_timestamp")

    # 1. Telemetry: Môi trường (nhiệt độ, độ ẩm, co2, khói)
    if "/telemetry/room/" in topic and "/environment" in topic and room_id:
        ws_message["type"] = "telemetry_environment"
        ws_message["room_id"] = room_id
        await ws_manager.broadcast_to_room(room_id, ws_message)
        await ws_manager.broadcast(ws_message)

    # 2. Telemetry: Số người (occupancy counting IR)
    elif "/telemetry/room/" in topic and "/occupancy" in topic and room_id:
        ws_message["type"] = "telemetry_occupancy"
        ws_message["room_id"] = room_id
        await ws_manager.broadcast_to_room(room_id, ws_message)
        await ws_manager.broadcast(ws_message)

    # 3. Trạng thái phòng FSM (SAVING, LECTURE, EMERGENCY,...)
    elif "/room/" in topic and topic.endswith("/state") and room_id:
        ws_message["type"] = "room_state_change"
        ws_message["room_id"] = room_id
        await ws_manager.broadcast_to_room(room_id, ws_message)
        await ws_manager.broadcast(ws_message)

    # 4. Cảnh báo chênh lệch sĩ số (Discrepancy)
    elif "/room/" in topic and topic.endswith("/discrepancy") and room_id:
        ws_message["type"] = "room_discrepancy"
        ws_message["room_id"] = room_id
        ws_message["urgency"] = "high" if isinstance(inner, dict) and inner.get("status") != "MATCH" else "low"
        await ws_manager.broadcast_to_room(room_id, ws_message)
        await ws_manager.broadcast(ws_message)

    # 5. Sự kiện quét thẻ RFID
    elif "/event/room/" in topic and "/rfid" in topic:
        ws_message["type"] = "rfid_scan"
        if room_id:
            ws_message["room_id"] = room_id
            await ws_manager.broadcast_to_room(room_id, ws_message)
        await ws_manager.broadcast(ws_message)

    # 6. SỰ KIỆN ĐÁNG CHÚ Ý (NOTABLE EVENT) từ Edge Gateway
    # Topic: smartcampus/v1/event/room/{room_id}/notable
    # Đây là topic thiết kế để Edge phát tín hiệu cho AI Agent subscribe.
    elif "/event/room/" in topic and "/notable" in topic:
        ws_message["type"] = "notable_event"
        if room_id:
            ws_message["room_id"] = room_id
        severity = inner.get("severity", "warning") if isinstance(inner, dict) else "warning"
        ws_message["urgency"] = severity
        ws_message["event_type"] = inner.get("event_type") if isinstance(inner, dict) else "unknown"
        logger.info(
            "Notable event received on %s: [%s] %s",
            topic, severity.upper(), inner.get("title", "No title") if isinstance(inner, dict) else "",
        )
        if room_id:
            await ws_manager.broadcast_to_room(room_id, ws_message)
        await ws_manager.broadcast(ws_message)

    # 7. Device Heartbeat
    elif "/heartbeat" in topic and device_id:
        ws_message["type"] = "device_heartbeat"
        ws_message["device_id"] = device_id
        await ws_manager.send_to_admins(ws_message)

    # 8. Device Status / LWT
    elif "/device/" in topic and topic.endswith("/status") and device_id:
        ws_message["type"] = "device_status"
        ws_message["device_id"] = device_id
        status_val = inner.get("device_status") if isinstance(inner, dict) else ""
        if status_val == "offline":
            ws_message["urgency"] = "high"
        await ws_manager.broadcast(ws_message)

    # 9. Lệnh điều khiển phòng (Room Command)
    elif "/command/room/" in topic and room_id:
        ws_message["type"] = "room_command"
        ws_message["room_id"] = room_id
        await ws_manager.broadcast_to_room(room_id, ws_message)

    # 10. Phản hồi xác nhận lệnh từ thiết bị (Command ACK)
    elif "/ack/device/" in topic:
        ws_message["type"] = "command_ack"
        if device_id:
            ws_message["device_id"] = device_id
        await ws_manager.broadcast(ws_message)

    # 11. Đề xuất điều khiển từ AI Agent
    elif "ai/recommendation" in topic:
        ws_message["type"] = "ai_recommendation"
        ws_message["urgency"] = inner.get("urgency", "medium") if isinstance(inner, dict) else "medium"
        await ws_manager.send_to_role("admin", ws_message)
        await ws_manager.send_to_role("lecturer", ws_message)

    else:
        # Generic message
        ws_message["type"] = "mqtt_generic"
        await ws_manager.broadcast(ws_message)


async def mqtt_bridge_worker() -> None:
    """Background worker: kết nối MQTT broker và bridge messages tới WebSocket.

    Sử dụng aiomqtt (async MQTT client) để subscribe và forward.
    Auto-reconnect nếu bị disconnect.
    """
    try:
        import aiomqtt
    except ImportError:
        logger.warning(
            "aiomqtt not installed. MQTT bridge disabled. "
            "Install with: pip install aiomqtt"
        )
        return

    reconnect_delay = 5  # seconds

    while True:
        try:
            logger.info(
                "Connecting to MQTT broker at %s:%s...",
                settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT,
            )

            async with aiomqtt.Client(
                hostname=settings.MQTT_BROKER_HOST,
                port=settings.MQTT_BROKER_PORT,
                username=settings.MQTT_USERNAME or None,
                password=settings.MQTT_PASSWORD or None,
                identifier=settings.MQTT_CLIENT_ID,
            ) as client:
                # Subscribe tất cả campus topics
                for topic in MQTT_TOPICS:
                    await client.subscribe(topic)
                    logger.info("Subscribed to MQTT topic: %s", topic)

                logger.info("MQTT bridge connected and listening")

                # Listen loop
                async for message in client.messages:
                    try:
                        topic_str = str(message.topic)
                        payload_str = message.payload.decode("utf-8") if isinstance(message.payload, bytes) else str(message.payload)

                        try:
                            payload = json.loads(payload_str)
                        except json.JSONDecodeError:
                            payload = {"raw": payload_str}

                        logger.debug("MQTT message: topic=%s payload=%s", topic_str, payload)
                        await _handle_mqtt_message(topic_str, payload)

                    except Exception as e:
                        logger.error("Error processing MQTT message: %s", e)

        except asyncio.CancelledError:
            logger.info("MQTT bridge worker cancelled")
            break
        except Exception as e:
            logger.warning(
                "MQTT bridge disconnected: %s. Reconnecting in %ds...",
                e, reconnect_delay,
            )
            await asyncio.sleep(reconnect_delay)
