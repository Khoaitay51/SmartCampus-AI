"""
app/api/rfid.py
---------------
RFID card management router — registration, lookup.
FR-RF-01..05.
"""
from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user, require_role
from app.auth.models import CardRegistrationRequest, RFIDCard, User
from app.auth.schemas import (
    CardApproveRequest,
    CardRegistrationRequestResponse,
    CardRejectRequest,
    CardSimulateRequest,
    RFIDCardResponse,
    RFIDRegisterRequest,
)
from app.database.session import get_async_db
from app.websocket.manager import ws_manager
from app.websocket.mqtt_bridge import publish_mqtt_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rfid", tags=["RFID"])



@router.get("", response_model=list[RFIDCardResponse])
async def list_rfid_cards(
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin: liệt kê tất cả thẻ RFID."""
    result = await db.execute(select(RFIDCard).order_by(RFIDCard.created_at.desc()))
    cards = result.scalars().all()

    response = []
    for card in cards:
        user = await db.get(User, card.user_id) if card.user_id else None
        response.append(RFIDCardResponse(
            id=card.id,
            uid=card.uid,
            user_id=card.user_id,
            is_registered=card.is_registered,
            username=user.username if user else None,
            role=user.role if user else None,
        ))
    return response


@router.post("/register", response_model=RFIDCardResponse)
async def register_rfid(
    data: RFIDRegisterRequest,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin: đăng ký / assign thẻ RFID cho user.

    FR-RF-01: Khi quét thẻ chưa đăng ký → DTwin popup → admin assign.
    """
    # Check existing card
    existing = (await db.execute(select(RFIDCard).where(RFIDCard.uid == data.uid))).scalar()

    if existing and existing.is_registered:
        raise HTTPException(status_code=409, detail="RFID card already registered")

    if data.user_id:
        user = await db.get(User, data.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

    if existing:
        # Card đã unknown, update registration
        existing.user_id = data.user_id
        existing.is_registered = True
        existing.registered_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(existing)
        card = existing
    else:
        card = RFIDCard(
            uid=data.uid,
            user_id=data.user_id,
            is_registered=data.user_id is not None,
            registered_at=datetime.now(timezone.utc) if data.user_id else None,
        )
        db.add(card)
        await db.commit()
        await db.refresh(card)

    user = await db.get(User, card.user_id) if card.user_id else None
    return RFIDCardResponse(
        id=card.id,
        uid=card.uid,
        user_id=card.user_id,
        is_registered=card.is_registered,
        username=user.username if user else None,
        role=user.role if user else None,
    )


@router.get("/lookup/{uid}")
async def lookup_rfid(
    uid: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Internal: lookup thẻ RFID theo UID.

    Được gọi từ MQTT bridge khi ESP32 quét thẻ.
    Không cần auth (internal service call).
    """
    card = (await db.execute(select(RFIDCard).where(RFIDCard.uid == uid))).scalar()

    if not card:
        # FR-RF-01: Unknown card — tạo record chưa đăng ký
        card = RFIDCard(uid=uid, is_registered=False)
        db.add(card)
        await db.commit()
        await db.refresh(card)

        return {
            "status": "unknown",
            "uid": uid,
            "card_id": str(card.id),
            "message": "Card not registered. Forwarding to DTwin for assignment.",
        }

    if not card.is_registered or not card.user_id:
        return {
            "status": "unregistered",
            "uid": uid,
            "card_id": str(card.id),
        }

    user = await db.get(User, card.user_id)
    card.last_scanned_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "status": "registered",
        "uid": uid,
        "card_id": str(card.id),
        "user_id": str(user.id) if user else None,
        "username": user.username if user else None,
        "full_name": user.full_name if user else None,
        "role": user.role if user else None,
    }


# ---------------------------------------------------------------------------
# Corridor Node RFID Registration & Approval (FR-RF-01)
# ---------------------------------------------------------------------------

@router.get("/requests", response_model=list[CardRegistrationRequestResponse])
async def list_card_registration_requests(
    status: str | None = Query(None, description="Lọc theo trạng thái: pending | approved | rejected"),
    db: AsyncSession = Depends(get_async_db),
):
    """Lấy danh sách các yêu cầu đăng ký thẻ RFID quét tại node Hành lang (Corridor Node)."""
    stmt = select(CardRegistrationRequest).order_by(CardRegistrationRequest.created_at.desc())
    if status:
        stmt = stmt.where(CardRegistrationRequest.status == status.lower())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/requests/{request_id}/approve", response_model=CardRegistrationRequestResponse)
async def approve_card_registration_request(
    request_id: UUID,
    data: CardApproveRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Admin / Giảng viên phê duyệt thẻ RFID quét tại Hành lang.

    - Gán thẻ cho User (Sinh viên / Giảng viên).
    - Cập nhật bảng rfid_cards và card_registration_requests.
    - Gửi MQTT response về Corridor Node: ESP32 đổi LED xanh, còi beep ngắn, OLED 'DA DUYET / OK'.
    - Bắn WebSocket realtime tới giao diện Digital Twin.
    """
    req = await db.get(CardRegistrationRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu đăng ký thẻ")

    target_user: User | None = None
    if data.user_id:
        target_user = await db.get(User, data.user_id)
    elif data.username or data.full_name:
        uname = data.username or f"sv_{req.card_uid.replace(':', '').replace('-', '')[-6:]}"
        user_res = await db.execute(select(User).where(User.username == uname))
        target_user = user_res.scalar_one_or_none()
        if not target_user:
            from app.auth.service import hash_password
            target_user = User(
                username=uname,
                email=f"{uname}@smartcampus.edu.vn",
                full_name=data.full_name or uname,
                role=data.role or "student",
                hashed_password=hash_password("123456"),
                is_active=True,
            )
            db.add(target_user)
            await db.commit()
            await db.refresh(target_user)

    assigned_name = target_user.full_name if target_user else (data.full_name or "Sinh viên")
    req.status = "approved"
    req.assigned_user_id = target_user.id if target_user else None
    req.assigned_user_name = assigned_name
    req.updated_at = datetime.now(timezone.utc)

    # Cập nhật hoặc thêm vào RFIDCard
    card_res = await db.execute(select(RFIDCard).where(RFIDCard.uid == req.card_uid))
    rfid_card = card_res.scalar_one_or_none()
    if rfid_card:
        rfid_card.user_id = target_user.id if target_user else None
        rfid_card.is_registered = True
        rfid_card.registered_at = datetime.now(timezone.utc)
    else:
        rfid_card = RFIDCard(
            uid=req.card_uid,
            user_id=target_user.id if target_user else None,
            is_registered=True,
            registered_at=datetime.now(timezone.utc),
        )
        db.add(rfid_card)

    await db.commit()
    await db.refresh(req)

    # 1. Phát MQTT Response về Corridor Node
    resp_topic = f"smartcampus/v1/card/registration/response/{req.mac_address}" if req.mac_address else "smartcampus/v1/card/registration/response/broadcast"
    payload = {
        "message_id": str(uuid.uuid4()),
        "payload": {
            "request_id": str(req.request_id),
            "card_uid": req.card_uid,
            "status": "approved",
            "assigned_user_id": str(target_user.id) if target_user else None,
            "assigned_user_name": assigned_name,
            "message": f"Thẻ {req.card_uid} đã duyệt thành công",
        },
    }
    await publish_mqtt_message(resp_topic, payload)
    await publish_mqtt_message("smartcampus/v1/card/registration/response", payload)

    # 2. Bắn WebSocket thông báo tới Digital Twin
    await ws_manager.broadcast({
        "source": "api",
        "type": "card_registration_approved",
        "data": {
            "request_id": str(req.request_id),
            "card_uid": req.card_uid,
            "status": "approved",
            "assigned_user_name": assigned_name,
        },
    })

    return req


@router.post("/requests/{request_id}/reject", response_model=CardRegistrationRequestResponse)
async def reject_card_registration_request(
    request_id: UUID,
    data: CardRejectRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Admin / Giảng viên từ chối thẻ RFID quét tại Hành lang.

    - Cập nhật trạng thái 'rejected'.
    - Gửi MQTT response về Corridor Node: ESP32 đổi LED đỏ, còi dài, OLED 'TU CHOI'.
    - Bắn WebSocket realtime tới giao diện Digital Twin.
    """
    req = await db.get(CardRegistrationRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu đăng ký thẻ")

    reason = data.reason or "Thẻ bị từ chối phê duyệt"
    req.status = "rejected"
    req.note = f"{req.note or ''} | Từ chối: {reason}".strip(" |")
    req.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(req)

    # 1. Phát MQTT Response về Corridor Node
    resp_topic = f"smartcampus/v1/card/registration/response/{req.mac_address}" if req.mac_address else "smartcampus/v1/card/registration/response/broadcast"
    payload = {
        "message_id": str(uuid.uuid4()),
        "payload": {
            "request_id": str(req.request_id),
            "card_uid": req.card_uid,
            "status": "rejected",
            "assigned_user_id": None,
            "assigned_user_name": None,
            "message": reason,
        },
    }
    await publish_mqtt_message(resp_topic, payload)
    await publish_mqtt_message("smartcampus/v1/card/registration/response", payload)

    # 2. Bắn WebSocket thông báo tới Digital Twin
    await ws_manager.broadcast({
        "source": "api",
        "type": "card_registration_rejected",
        "data": {
            "request_id": str(req.request_id),
            "card_uid": req.card_uid,
            "status": "rejected",
            "reason": reason,
        },
    })

    return req


@router.post("/requests/simulate", response_model=dict)
async def simulate_corridor_card_scan(
    data: CardSimulateRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Mô phỏng quẹt thẻ lạ tại Corridor Node (FR-RF-01).

    Phát MQTT topic `smartcampus/v1/card/registration/request` như bo mạch ESP32 thật.
    Cho phép kiểm thử toàn diện quy trình quét → alert → duyệt thẻ.
    """
    card_uid = data.card_uid or f"RFID_{random.randint(1000, 9999)}_{random.choice(['A1', 'B2', 'C3', 'D4'])}"
    mac = data.mac_address or "24:6F:28:AA:BB:CC"

    payload = {
        "message_id": str(uuid.uuid4()),
        "source_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "mac_address": mac,
            "card_uid": card_uid,
            "room_id": data.room_id or "corridor-node-01",
            "status": "pending",
            "node_role": "corridor",
            "note": "Quét thẻ mô phỏng tại Corridor Node (Test Demo)",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    success = await publish_mqtt_message("smartcampus/v1/card/registration/request", payload)

    return {
        "success": success,
        "message": f"Đã phát sự kiện quét thẻ {card_uid} tại Corridor Node ({mac})",
        "card_uid": card_uid,
        "mac_address": mac,
    }

