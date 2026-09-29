"""
app/api/users.py
----------------
User management router — Admin CRUD operations.
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.auth.models import User
from app.auth.schemas import UserListResponse, UserResponse
from app.database.session import get_async_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("", response_model=UserListResponse)
async def list_users(
    role: str | None = None,
    skip: int = 0,
    limit: int = 50,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin: liệt kê tất cả users, filter theo role."""
    query = select(User)
    count_query = select(func.count(User.id))

    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(query.offset(skip).limit(limit).order_by(User.created_at.desc()))
    users = result.scalars().all()

    return UserListResponse(users=[UserResponse.model_validate(u) for u in users], total=total)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    _admin: User = Depends(require_role("admin", "lecturer")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin/Lecturer: xem chi tiết user."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}/lock")
async def toggle_lock_user(
    user_id: UUID,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin: lock/unlock user account."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_locked = not user.is_locked
    await db.commit()
    return {"user_id": str(user_id), "is_locked": user.is_locked}


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db),
):
    """Admin: xóa user."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(user)
    await db.commit()
    return {"message": "User deleted", "user_id": str(user_id)}
