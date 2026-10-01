"""
app/auth/schemas.py
-------------------
Pydantic schemas cho authentication & user management.
Tham khảo pattern từ webdeb auth/schema.py, mở rộng cho SmartCampus.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator



# ---------------------------------------------------------------------------
# Auth Schemas
# ---------------------------------------------------------------------------

class UserSignUp(BaseModel):
    """Schema đăng ký tài khoản mới."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Mật khẩu 8-128 ký tự, ít nhất 1 chữ cái và 1 chữ số.",
    )
    full_name: Optional[str] = None
    role: str = Field(default="student", description="Role: admin, lecturer, student")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value):
            raise ValueError("Mật khẩu phải chứa ít nhất một chữ cái.")
        if not re.search(r"\d", value):
            raise ValueError("Mật khẩu phải chứa ít nhất một chữ số.")
        if " " in value:
            raise ValueError("Mật khẩu không được chứa khoảng trắng.")
        return value

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in ("admin", "lecturer", "student"):
            raise ValueError("Role phải là: admin, lecturer, hoặc student.")
        return value


class UserLogin(BaseModel):
    """Schema login — dùng cho JSON body (ngoài OAuth2 form)."""
    email: str
    password: str


class TokenResponse(BaseModel):
    """Response trả về sau login."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Data decoded từ JWT token."""
    user_id: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None


# ---------------------------------------------------------------------------
# User Response Schemas
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    """Public user info response."""
    id: UUID
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    is_locked: bool
    avatar_url: Optional[str] = None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Paginated user list."""
    users: list[UserResponse]
    total: int


class AuthRegisterResponse(BaseModel):
    """Response sau khi đăng ký thành công."""
    message: str
    user_name: str
    user_email: str
    user_id: UUID
    user_role: Optional[str] = None


# ---------------------------------------------------------------------------
# RFID Schemas
# ---------------------------------------------------------------------------

class RFIDRegisterRequest(BaseModel):
    """Request đăng ký thẻ RFID cho user."""
    uid: str = Field(..., min_length=4, max_length=50)
    user_id: Optional[UUID] = None
    role: Optional[str] = None
    full_name: Optional[str] = None


class RFIDCardResponse(BaseModel):
    """Response thông tin thẻ RFID."""
    id: UUID
    uid: str
    user_id: Optional[UUID] = None
    is_registered: bool
    username: Optional[str] = None
    role: Optional[str] = None

    model_config = {"from_attributes": True}


class CardRegistrationRequestResponse(BaseModel):
    """Response cho bản ghi yêu cầu duyệt thẻ từ Corridor Node."""
    request_id: UUID
    card_uid: str
    mac_address: Optional[str] = None
    room_id: Optional[UUID] = None
    status: str
    assigned_user_id: Optional[UUID] = None
    assigned_user_name: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CardApproveRequest(BaseModel):
    """Request phê duyệt gán thẻ RFID cho user/sinh viên."""
    user_id: Optional[UUID] = None
    full_name: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = "student"


class CardRejectRequest(BaseModel):
    """Request từ chối duyệt thẻ RFID."""
    reason: Optional[str] = None


class CardSimulateRequest(BaseModel):
    """Request mô phỏng quẹt thẻ lạ tại Corridor Node."""
    card_uid: Optional[str] = None
    mac_address: Optional[str] = "24:6F:28:AA:BB:CC"
    room_id: Optional[str] = None

