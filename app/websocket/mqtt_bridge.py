"""
app/websocket/mqtt_bridge.py
----------------------------
MQTT → WebSocket bridge — subscribe tất cả campus MQTT topics từ SmartCampus-edge,
forward messages tới WebSocket clients realtime. Đồng thời thực hiện Giải pháp 3 (Auto-Sync DB)
và lắng nghe Notable Event topic để kích hoạt AI ReAct Agent tự động.

FR-DT-07: Latency < 200ms từ ESP32/Edge đến DTwin update.
FR-AI-05: Human-In-The-Loop AI Recommendation.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any
import uuid
from uuid import UUID

from sqlalchemy import select

from app.api.evaluate import get_agent
from app.campus.models import AIRecommendation, Device, Room
from app.config.settings import settings
from app.database.session import get_db_context
from app.logging.audit import save_audit_and_memory
from app.schemas.context import (
    Occupancy,
    OperationalContext,
    RoomInfo,
    SensorsStats,
    TelemetrySummary,
)
from app.schemas.events import EventPayload, EventType
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
    # RFID Card Registration (Corridor Node FR-RF-01)
    "smartcampus/v1/card/registration/#",
]

# Debounce cache cho việc gọi Agent theo room và event type (giới hạn 30s giữa các lần gọi)
_AGENT_COOLDOWN: dict[str, float] = {}
_global_mqtt_client: Any | None = None


async def publish_mqtt_message(topic: str, payload: dict[str, Any]) -> bool:
    """Publish MQTT message to Mosquitto broker (used for card registration responses or simulations)."""
    global _global_mqtt_client
    try:
        payload_bytes = json.dumps(payload).encode("utf-8")
        if _global_mqtt_client is not None:
            await _global_mqtt_client.publish(topic, payload_bytes)
            logger.info("Published MQTT to %s via active bridge: %s", topic, payload)
            return True
        import aiomqtt
        async with aiomqtt.Client(
            hostname=settings.MQTT_BROKER_HOST,
            port=settings.MQTT_BROKER_PORT,
            username=settings.MQTT_USERNAME or None,
            password=settings.MQTT_PASSWORD or None,
            identifier=f"{settings.MQTT_CLIENT_ID}-pub-{uuid.uuid4().hex[:6]}",
        ) as pub_client:
            await pub_client.publish(topic, payload_bytes)
            logger.info("Published MQTT to %s via ad-hoc client: %s", topic, payload)
            return True
    except Exception as e:
        logger.error("Failed to publish MQTT message to %s: %s", topic, e)
        return False


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


async def _auto_sync_room_and_device(
    topic: str,
    inner: Any,
    room_id: str | None,
    device_id: str | None,
) -> None:
    """Giải pháp 3: Auto-Upsert Realtime sync giữa Edge/Firmware và AI Backend database.

    Tự động đồng bộ Room và Device vào schema `campus` khi nhận bất kỳ MQTT message nào,
    cập nhật cache telemetry mới nhất và ngăn ngừa mọi lỗi lệch UUID / Foreign Key.
    """
    if not isinstance(inner, dict):
        inner = {}

    target_room_uuid: UUID | None = None
    if room_id:
        try:
            target_room_uuid = UUID(room_id)
        except (ValueError, TypeError):
            target_room_uuid = None

    async with get_db_context() as db:
        try:
            # 1. Đồng bộ Room
            if target_room_uuid is not None:
                stmt = select(Room).where(Room.id == target_room_uuid)
                result = await db.execute(stmt)
                room = result.scalar_one_or_none()
                if not room:
                    room_name = f"Phòng {str(target_room_uuid)[:8]}"
                    if str(target_room_uuid) == "11111111-1111-1111-1111-111111111111":
                        room_name = "Phong Hoc Thong Minh 402"
                    elif str(target_room_uuid) == "11111111-1111-1111-1111-111111111110":
                        room_name = "Hanh Lang Tang 4"

                    mode_val = inner.get("current_mode") or inner.get("mode") or "SAVING"
                    valid_modes = ('SAVING', 'SELF_STUDY', 'LECTURE', 'EXAM', 'LOCK', 'SUSPECTED', 'EMERGENCY')
                    if mode_val not in valid_modes:
                        mode_val = "SAVING"

                    room = Room(
                        id=target_room_uuid,
                        name=room_name,
                        building="A",
                        floor=4,
                        capacity=40,
                        mode=mode_val,
                    )
                    db.add(room)
                    await db.flush()
                    logger.info("Auto-sync: Đã khởi tạo Room %s (%s) trong campus.rooms", room_name, target_room_uuid)

                # Cập nhật telemetry cache nếu có
                if "temperature" in inner and inner["temperature"] is not None:
                    try:
                        room.temperature = float(inner["temperature"])
                    except (ValueError, TypeError):
                        pass
                if "humidity" in inner and inner["humidity"] is not None:
                    try:
                        room.humidity = float(inner["humidity"])
                    except (ValueError, TypeError):
                        pass
                if "co2" in inner and inner["co2"] is not None:
                    try:
                        room.co2 = float(inner["co2"])
                    except (ValueError, TypeError):
                        pass
                if "occupancy" in inner and inner["occupancy"] is not None:
                    try:
                        room.occupancy = int(inner["occupancy"])
                    except (ValueError, TypeError):
                        pass
                elif "count" in inner and inner["count"] is not None and "/occupancy" in topic:
                    try:
                        room.occupancy = int(inner["count"])
                    except (ValueError, TypeError):
                        pass

                new_mode = inner.get("current_mode") or (inner.get("mode") if "/state" in topic else None)
                valid_modes = ('SAVING', 'SELF_STUDY', 'LECTURE', 'EXAM', 'LOCK', 'SUSPECTED', 'EMERGENCY')
                if new_mode and new_mode in valid_modes:
                    if room.mode != new_mode:
                        room.previous_mode = room.mode
                        room.mode = new_mode

            # 2. Đồng bộ Device
            if device_id:
                stmt_d = select(Device).where(Device.mac_address == device_id)
                res_d = await db.execute(stmt_d)
                dev = res_d.scalar_one_or_none()
                if not dev:
                    dev = Device(
                        mac_address=device_id,
                        name=f"ESP32-{device_id[-4:] if len(device_id) >= 4 else device_id}",
                        device_type="sensor_node",
                        room_id=target_room_uuid,
                        status="online",
                        last_heartbeat=datetime.now(timezone.utc),
                    )
                    db.add(dev)
                    logger.info("Auto-sync: Đã đăng ký Device MAC=%s vào Room=%s", device_id, target_room_uuid)
                else:
                    dev.last_heartbeat = datetime.now(timezone.utc)
                    if "/status" in topic:
                        st = inner.get("device_status") or inner.get("status")
                        if st in ("online", "offline", "provisioning"):
                            dev.status = st
                    else:
                        dev.status = "online"
                    if target_room_uuid and not dev.room_id:
                        dev.room_id = target_room_uuid

            await db.commit()
        except Exception as err:
            await db.rollback()
            logger.warning("Auto-sync room/device warning: %s", err)


async def _run_agent_task(
    room_id_str: str,
    inner: dict[str, Any],
    topic: str,
    client: Any,
) -> None:
    """Tác vụ nền chạy ReActXenAgent không block MQTT worker."""
    logger.info("Bắt đầu xử lý ReActXenAgent cho sự kiện đáng chú ý tại phòng %s...", room_id_str)
    try:
        room_uuid = UUID(room_id_str)
    except (ValueError, TypeError):
        logger.warning("Room ID không hợp lệ cho Agent: %s", room_id_str)
        return

    # Lấy thông tin phòng hiện tại từ database
    room_name = f"Phòng {room_id_str[:8]}"
    current_mode = "SAVING"
    smoke_state = "NORMAL"
    temp_val = 26.0
    hum_val = 60.0
    co2_val = 450.0
    occ_val = 0

    async with get_db_context() as db:
        r = await db.get(Room, room_uuid)
        if r:
            room_name = r.name
            current_mode = r.mode
            temp_val = r.temperature or 26.0
            hum_val = r.humidity or 60.0
            co2_val = r.co2 or 450.0
            occ_val = r.occupancy or 0

    ev_data = inner.get("event_data", {}) if isinstance(inner.get("event_data"), dict) else {}
    if "smoke_state" in ev_data:
        smoke_state = ev_data["smoke_state"]
    elif inner.get("event_type") == "smoke_detected":
        smoke_state = "EMERGENCY" if inner.get("severity") == "critical" else "SUSPECTED"

    # Map EventType
    raw_ev_type = inner.get("event_type", "manual_trigger")
    try:
        ev_type = EventType(raw_ev_type)
    except ValueError:
        ev_type = EventType.MANUAL_TRIGGER

    event_id_str = inner.get("event_id") or str(uuid.uuid4())
    try:
        ev_uuid = UUID(event_id_str)
    except (ValueError, TypeError):
        ev_uuid = uuid.uuid4()

    event = EventPayload(
        event_id=ev_uuid,
        event_type=ev_type,
        room_id=room_uuid,
        timestamp=datetime.now(timezone.utc),
        event_data=inner,
        operational_context={},
    )

    now_dt = datetime.now(timezone.utc)
    room_info = RoomInfo(
        room_id=room_uuid,
        room_name=room_name,
        room_type="classroom",
        current_mode=current_mode,
        smoke_state=smoke_state,
    )
    def stat(v: float) -> SensorsStats:
        return SensorsStats(min=v, max=v, avg=v, latest=v)

    telemetry_sum = TelemetrySummary(
        window_start=now_dt,
        window_end=now_dt,
        temperature=stat(temp_val),
        humidity=stat(hum_val),
        co2=stat(co2_val),
        smoke_value=stat(float(ev_data.get("smoke_value", 50.0))),
        air_quality=stat(50.0),
    )
    occupancy = Occupancy(
        current_count=occ_val,
        total_in=occ_val,
        total_out=0,
        trend="stable",
    )
    context = OperationalContext(
        room=room_info,
        telemetry_summary=telemetry_sum,
        occupancy=occupancy,
        active_session=None,
        recent_events=[inner],
    )
    event.operational_context = context.model_dump(mode="json")

    # Run agent evaluation
    agent = get_agent()
    try:
        logger.info("Chạy ReActXenAgent.evaluate() cho event_id=%s, type=%s", ev_uuid, ev_type)
        response = await agent.evaluate(event=event, context=context)
        logger.info("Agent hoàn tất phân tích: skip=%s, rec=%s", response.skip, response.recommendation)
    except Exception as exc:
        logger.error("Lỗi khi chạy ReActXenAgent: %s", exc, exc_info=True)
        return

    # Lưu audit log & pgvector memory
    try:
        await save_audit_and_memory(event, response)
    except Exception as e:
        logger.warning("Lưu audit/memory thất bại: %s", e)

    # Nếu có đề xuất điều khiển và không skip -> tạo AI Recommendation (HITL hoặc Autopilot)
    if response.recommendation and not response.skip:
        from app.campus.hitl import is_hitl_enabled, dispatch_tool_execution
        rec_params = getattr(response.recommendation, "tool_params", getattr(response.recommendation, "parameters", {}))
        
        hitl_active = is_hitl_enabled()
        status_init = "pending" if hitl_active else "auto_approved"

        rec_obj = AIRecommendation(
            event_id=str(event.event_id),
            room_id=room_uuid,
            tool_name=response.recommendation.tool_name,
            tool_params=rec_params,
            reason=response.recommendation.reason,
            confidence=response.recommendation.confidence,
            urgency=response.recommendation.urgency,
            status=status_init,
            review_notes="Tự động phê duyệt và thực thi qua chế độ Autopilot" if not hitl_active else None,
            reviewed_at=datetime.now(timezone.utc) if not hitl_active else None,
        )
        async with get_db_context() as db:
            db.add(rec_obj)
            await db.commit()
            await db.refresh(rec_obj)
            rec_id_str = str(rec_obj.id)

        rec_data = {
            "type": "ai_recommendation",
            "id": rec_id_str,
            "recommendation_id": rec_id_str,
            "event_id": str(event.event_id),
            "room_id": str(room_uuid),
            "room_name": room_name,
            "tool_name": response.recommendation.tool_name,
            "tool_params": rec_params,
            "reason": response.recommendation.reason,
            "confidence": response.recommendation.confidence,
            "urgency": response.recommendation.urgency,
            "analysis": response.analysis,
            "is_fallback": response.is_fallback,
            "requires_confirmation": hitl_active,
            "hitl_enabled": hitl_active,
            "auto_executed": not hitl_active,
            "edge_rest_endpoint": "http://localhost:8000/api/commands/room/execute",
        }

        # Broadcast WebSocket tới Digital Twin UI (hiển thị popup HITL hoặc thông báo Auto-pilot)
        await ws_manager.broadcast(rec_data)

        # Publish MQTT topic smartcampus/v1/ai/recommendation
        if client:
            try:
                await client.publish("smartcampus/v1/ai/recommendation", json.dumps(rec_data))
                logger.info("Đã publish AI recommendation lên MQTT: %s", rec_id_str)
            except Exception as pe:
                logger.warning("Không thể publish AI recommendation lên MQTT: %s", pe)

        # Nếu chế độ HITL tắt -> Tự động thực thi lệnh ngay lập tức!
        if not hitl_active:
            logger.info("⚡ [AUTOPILOT] HITL đang tắt. Tự động thực thi tool '%s' xuống Edge Gateway...", response.recommendation.tool_name)
            await dispatch_tool_execution(
                rec_id=rec_id_str,
                room_id=room_uuid,
                tool_name=response.recommendation.tool_name,
                tool_params=rec_params,
                reason=response.recommendation.reason or "Auto-pilot execution without manual approval",
                operator="AI_AUTOPILOT",
                is_auto=True,
            )



async def _trigger_agent_from_notable_event(
    room_id: str | None,
    inner: dict[str, Any],
    topic: str,
    client: Any,
) -> None:
    """Lắng nghe topic notable event từ Edge và kích hoạt AI ReAct Agent."""
    if not room_id:
        return

    event_type_str = inner.get("event_type", "manual_trigger")
    cooldown_key = f"{room_id}:{event_type_str}"
    loop_now = asyncio.get_event_loop().time()
    last_trigger = _AGENT_COOLDOWN.get(cooldown_key, 0.0)
    if (loop_now - last_trigger) < 30.0:
        logger.info("Debounce agent trigger cho %s (còn %0.1fs cooldown)", cooldown_key, 30.0 - (loop_now - last_trigger))
        return
    _AGENT_COOLDOWN[cooldown_key] = loop_now

    asyncio.create_task(_run_agent_task(room_id, inner, topic, client))


async def _handle_mqtt_message(
    topic: str,
    raw_payload: dict[str, Any],
    client: Any = None,
) -> None:
    """Route MQTT message tới WebSocket clients và tự động đồng bộ DB / gọi Agent."""
    room_id = _parse_room_id_from_topic(topic)
    device_id = _parse_device_mac_from_topic(topic)

    # Edge chuẩn hóa envelope: {"message_id": "...", "source_timestamp": "...", "payload": {...}}
    inner = raw_payload.get("payload", raw_payload) if isinstance(raw_payload, dict) else raw_payload

    # Thực hiện Giải pháp 3: Tự động đồng bộ Room & Device vào Database
    asyncio.create_task(_auto_sync_room_and_device(topic, inner, room_id, device_id))

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

    # 6. SỰ KIỆN ĐÁNG CHÚ Ý (NOTABLE EVENT) từ Edge Gateway -> Kích hoạt AI Agent
    elif "/event/room/" in topic and "/notable" in topic:
        ws_message["type"] = "notable_event"
        if room_id:
            ws_message["room_id"] = room_id
        severity = inner.get("severity", "warning") if isinstance(inner, dict) else "warning"
        ws_message["urgency"] = severity
        ws_message["event_type"] = inner.get("event_type") if isinstance(inner, dict) else "unknown"
        logger.info(
            "Notable event received on %s: [%s] %s -> Triggering AI Agent listener",
            topic, severity.upper(), inner.get("title", "No title") if isinstance(inner, dict) else "",
        )
        if room_id:
            await ws_manager.broadcast_to_room(room_id, ws_message)
        await ws_manager.broadcast(ws_message)

        # Kích hoạt Agent xử lý bất đồng bộ
        if isinstance(inner, dict):
            await _trigger_agent_from_notable_event(room_id, inner, topic, client)

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
        rec_id = inner.get("id") or inner.get("recommendation_id") if isinstance(inner, dict) else None
        if rec_id:
            ws_message["id"] = rec_id
            ws_message["recommendation_id"] = rec_id
        ws_message["urgency"] = inner.get("urgency", "medium") if isinstance(inner, dict) else "medium"
        await ws_manager.send_to_role("admin", ws_message)
        await ws_manager.send_to_role("lecturer", ws_message)

    # 12. Quét & Đăng ký thẻ RFID tại Node Hành lang (Corridor Node FR-RF-01)
    elif "/card/registration/request" in topic:
        ws_message["type"] = "card_registration_request"
        ws_message["urgency"] = "medium"
        card_uid = inner.get("card_uid") if isinstance(inner, dict) else None
        mac_address = inner.get("mac_address") if isinstance(inner, dict) else None
        note = inner.get("note", "Quét tại Node Hành lang (Corridor Node)") if isinstance(inner, dict) else "Quét tại Node Hành lang"

        if card_uid:
            try:
                from app.auth.models import CardRegistrationRequest
                async with get_db_context() as db:
                    res = await db.execute(
                        select(CardRegistrationRequest).where(
                            CardRegistrationRequest.card_uid == card_uid,
                            CardRegistrationRequest.status == "pending",
                        ).limit(1)
                    )
                    existing = res.scalar_one_or_none()
                    if not existing:
                        new_req = CardRegistrationRequest(
                            card_uid=card_uid,
                            mac_address=mac_address,
                            status="pending",
                            note=note,
                        )
                        db.add(new_req)
                        await db.commit()
                        await db.refresh(new_req)
                        if isinstance(inner, dict):
                            inner["request_id"] = str(new_req.request_id)
                    else:
                        if isinstance(inner, dict):
                            inner["request_id"] = str(existing.request_id)
            except Exception as e:
                logger.error("Lỗi khi lưu CardRegistrationRequest: %s", e)

        await ws_manager.broadcast(ws_message)

    elif "/card/registration/response" in topic:
        ws_message["type"] = "card_registration_response"
        await ws_manager.broadcast(ws_message)

    else:
        # Generic message
        ws_message["type"] = "mqtt_generic"
        await ws_manager.broadcast(ws_message)


async def mqtt_bridge_worker() -> None:
    """Background worker: kết nối MQTT broker và bridge messages tới WebSocket.

    Sử dụng aiomqtt (async MQTT client) để subscribe và forward.
    Auto-reconnect nếu bị disconnect.
    """
    global _global_mqtt_client
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
                _global_mqtt_client = client
                # Subscribe tất cả campus topics
                for topic in MQTT_TOPICS:
                    await client.subscribe(topic)
                    logger.info("Subscribed to MQTT topic: %s", topic)

                logger.info("MQTT bridge connected and listening")

                # Listen loop
                try:
                    async for message in client.messages:
                        try:
                            topic_str = str(message.topic)
                            payload_str = message.payload.decode("utf-8") if isinstance(message.payload, bytes) else str(message.payload)

                            try:
                                payload = json.loads(payload_str)
                            except json.JSONDecodeError:
                                payload = {"raw": payload_str}

                            logger.debug("MQTT message: topic=%s payload=%s", topic_str, payload)
                            await _handle_mqtt_message(topic_str, payload, client=client)

                        except Exception as e:
                            logger.error("Error processing MQTT message: %s", e)
                finally:
                    _global_mqtt_client = None


        except asyncio.CancelledError:
            logger.info("MQTT bridge worker cancelled")
            break
        except Exception as e:
            logger.warning(
                "MQTT bridge disconnected: %s. Reconnecting in %ds...",
                e, reconnect_delay,
            )
            await asyncio.sleep(reconnect_delay)
