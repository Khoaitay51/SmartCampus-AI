"""
app/api/auth.py
---------------
Authentication router: signup, login, root admin creation.
Tham khảo pattern từ webdeb feature/auth/router.py.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user, require_role
from app.auth.models import User
from app.auth.schemas import (
    AuthRegisterResponse,
    TokenResponse,
    UserResponse,
    UserSignUp,
)
from app.auth.service import create_access_token, hash_password, verify_password
from app.database.session import get_async_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------------------------------------------------------
# Root Admin (1 lần duy nhất)
# ---------------------------------------------------------------------------

@router.post("/rootadmin", response_model=dict[str, Any])
async def create_root_admin(db: AsyncSession = Depends(get_async_db)):
    """Tạo root admin user (chỉ chạy 1 lần đầu)."""
    email = "admin@smartcampus.local"
    username = "admin"
    password = "admin123456"

    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        return {
            "message": "Root admin already exists",
            "user_id": str(existing.id),
            "username": existing.username,
            "email": existing.email,
        }

    admin = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        full_name="System Administrator",
        role="admin",
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)

    return {
        "message": "Root admin created successfully",
        "user_id": str(admin.id),
        "username": admin.username,
        "email": admin.email,
        "default_password": "admin123456 (CHANGE THIS!)",
    }


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------

@router.post("/signup", response_model=AuthRegisterResponse)
async def signup(
    user_data: UserSignUp,
    db: AsyncSession = Depends(get_async_db),
):
    """Đăng ký tài khoản mới (student mặc định)."""
    # Check duplicates
    existing_email = (await db.execute(select(User).where(User.email == user_data.email))).scalar()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already exists")

    existing_username = (await db.execute(select(User).where(User.username == user_data.username))).scalar()
    if existing_username:
        raise HTTPException(status_code=400, detail="Username already exists")

    # Chỉ admin mới tạo được admin/lecturer role — public signup luôn là student
    role = "student"

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        role=role,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return AuthRegisterResponse(
        message="User created successfully",
        user_name=new_user.username,
        user_email=new_user.email,
        user_id=new_user.id,
        user_role=new_user.role,
    )


# ---------------------------------------------------------------------------
# Admin creates user with any role
# ---------------------------------------------------------------------------

@router.post("/create-user", response_model=AuthRegisterResponse)
async def admin_create_user(
    user_data: UserSignUp,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin tạo user với role tùy ý (admin/lecturer/student)."""
    existing_email = (await db.execute(select(User).where(User.email == user_data.email))).scalar()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already exists")

    existing_username = (await db.execute(select(User).where(User.username == user_data.username))).scalar()
    if existing_username:
        raise HTTPException(status_code=400, detail="Username already exists")

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return AuthRegisterResponse(
        message=f"{user_data.role.capitalize()} user created successfully",
        user_name=new_user.username,
        user_email=new_user.email,
        user_id=new_user.id,
        user_role=new_user.role,
    )


# ---------------------------------------------------------------------------
# Login (OAuth2PasswordRequestForm — tương thích webdeb frontend)
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_async_db),
):
    """Login bằng email + password, trả về JWT token.

    Dùng OAuth2PasswordRequestForm để tương thích cả Swagger UI lẫn frontend.
    Field 'username' của form nhận email (giống webdeb pattern).
    """
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    if user.is_locked:
        raise HTTPException(status_code=403, detail="Account is locked. Please contact admin.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated.")

    access_token = create_access_token(
        data={
            "user_id": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role,
        }
    )
    return TokenResponse(access_token=access_token, token_type="bearer")


# ---------------------------------------------------------------------------
# Current User Profile
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """Lấy thông tin user hiện tại từ JWT token."""
    return current_user
