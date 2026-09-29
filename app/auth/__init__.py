"""
app/auth/
---------
Module xác thực RBAC + JWT cho SmartCampus AI.
Roles: admin, lecturer (GV), student (SV).
"""
from app.auth.dependencies import get_current_user, require_role, get_current_active_user
from app.auth.service import (
    hash_password,
    verify_password,
    create_access_token,
    verify_access_token,
)

__all__ = [
    "get_current_user",
    "get_current_active_user",
    "require_role",
    "hash_password",
    "verify_password",
    "create_access_token",
    "verify_access_token",
]
