"""
app/auth/models.py
------------------
SQLAlchemy models cho User và RFIDCard.
Dựa trên pattern từ webdeb User model, mở rộng cho SmartCampus RBAC.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.models import Base


class User(Base):
    """Bảng users — Hỗ trợ 3 roles: admin, lecturer, student."""
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'lecturer', 'student')",
            name="check_user_role",
        ),
        {"schema": "campus"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(20), nullable=False, default="student")
    is_active = Column(Boolean, nullable=False, default=True)
    is_locked = Column(Boolean, nullable=False, default=False)
    avatar_url = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    rfid_cards = relationship("RFIDCard", back_populates="user", cascade="all, delete-orphan")


class RFIDCard(Base):
    """Bảng rfid_cards — Mapping UID thẻ RFID → User."""
    __tablename__ = "rfid_cards"
    __table_args__ = {"schema": "campus"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uid = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("campus.users.id"), nullable=True)
    is_registered = Column(Boolean, nullable=False, default=False)
    registered_at = Column(DateTime(timezone=True), nullable=True)
    last_scanned_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="rfid_cards")


class CardRegistrationRequest(Base):
    """Bảng card_registration_requests — Lưu các yêu cầu duyệt thẻ RFID quét tại Corridor Node."""
    __tablename__ = "card_registration_requests"
    __table_args__ = {"schema": "campus"}

    request_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    card_uid = Column(String(50), nullable=False, index=True)
    device_id = Column(UUID(as_uuid=True), nullable=True)
    room_id = Column(UUID(as_uuid=True), nullable=True)
    mac_address = Column(String(50), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)  # pending, approved, rejected
    assigned_user_id = Column(UUID(as_uuid=True), ForeignKey("campus.users.id"), nullable=True)
    assigned_user_name = Column(String(255), nullable=True)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc), nullable=True)
    processed_by = Column(UUID(as_uuid=True), ForeignKey("campus.users.id"), nullable=True)

    user = relationship("User", foreign_keys=[assigned_user_id])
