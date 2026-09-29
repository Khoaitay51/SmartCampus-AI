"""
app/api/rfid.py
---------------
RFID card management router — registration, lookup.
FR-RF-01..05.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user, require_role
from app.auth.models import RFIDCard, User
from app.auth.schemas import RFIDCardResponse, RFIDRegisterRequest
from app.database.session import get_async_db

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
