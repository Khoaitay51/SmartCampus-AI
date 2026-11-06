"""
app/config/safety.py
--------------------
Helper đọc động 4 cờ cấu hình an toàn (M1–M4 Ablation Study) từ biến môi trường
hoặc ``app.config.settings.settings`` mà không bắt buộc import các dependency nặng.
"""
from __future__ import annotations

import os

_FALSY = frozenset({"0", "false", "no", "off"})


def _read_flag(env_name: str, default: bool = True) -> bool:
    raw = os.getenv(env_name)
    if raw is not None:
        return raw.strip().lower() not in _FALSY
    try:
        from app.config.settings import settings

        val = getattr(settings, env_name, default)
        if isinstance(val, bool):
            return val
        return str(val).strip().lower() not in _FALSY
    except Exception:
        return default


def prompt_guard_enabled() -> bool:
    """Bật/tắt tầng bảo vệ M2: ActionToolPolicy, Review/Reflect loop và Confidence threshold."""
    return _read_flag("SAFETY_PROMPT_GUARD_ENABLED", True)


def fsm_enabled() -> bool:
    """Bật/tắt tầng bảo vệ M3: Ma trận phân quyền tool theo FSM mode (False = Global Tool Mode)."""
    return _read_flag("SAFETY_FSM_ENABLED", True)


def hitl_env_enabled() -> bool:
    """Bật/tắt tầng bảo vệ M4: Cổng phê duyệt con người (HITL) và chốt chặn Tier-2 Autopilot."""
    return _read_flag("SAFETY_HITL_ENABLED", True)


def toctou_binding_enabled() -> bool:
    """Bật/tắt ràng buộc Consent-Integrity (payload_hash) và Physical-TOCTOU (expected_state_version)."""
    return _read_flag("SAFETY_TOCTOU_BINDING_ENABLED", True)
