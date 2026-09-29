"""
app/auth/dependencies.py
------------------------
FastAPI dependencies cho authentication & RBAC.
Tham khảo pattern từ webdeb feature/user/service.py (get_current_user, require_admin).
Mở rộng thành require_role() linh hoạt cho 3 roles.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import TokenData
from app.auth.service import verify_access_token
from app.database.session import get_async_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """Dependency: decode JWT → lookup User từ database.

    Pattern tương tự webdeb get_current_user nhưng dùng async context manager.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_access_token(token)
    if payload is None:
        raise credentials_exception

    user_email: str | None = payload.get("email")
    if user_email is None:
        raise credentials_exception

    result = await db.execute(select(User).where(User.email == user_email))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency: kiểm tra user active và chưa bị lock."""
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="User account is deactivated")
    if current_user.is_locked:
        raise HTTPException(status_code=403, detail="Account is locked. Please contact admin.")
    return current_user


def require_role(*allowed_roles: str):
    """Factory dependency: kiểm tra user có role phù hợp.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role("admin"))):
            ...

        @router.get("/staff")
        async def staff_endpoint(user: User = Depends(require_role("admin", "lecturer"))):
            ...
    """

    async def _check_role(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(allowed_roles)}. "
                       f"Your role: {current_user.role}",
            )
        return current_user

    return _check_role
