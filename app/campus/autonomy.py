"""
app/campus/autonomy.py
----------------------
Logic quyết định Tiered Autonomy vs Full Autopilot (hàm thuần, không phụ thuộc DB/MQTT).
"""
from __future__ import annotations

import logging

from app.config.safety import hitl_env_enabled

logger = logging.getLogger(__name__)

# Tier-2 Critical Safety Tools (Cửa / FSM / Chuông)
TIER2_CRITICAL_TOOLS: frozenset[str] = frozenset(
    {"set_door", "door_control", "set_mode", "mode_control", "trigger_buzzer", "buzzer_control"}
)

# Ngưỡng tin cậy tối thiểu cho Autopilot đối với lệnh đảo nghịch được (Tier-1: quạt, đèn)
AUTOPILOT_MIN_CONFIDENCE: float = 0.8


def decide_autonomy(
    tool_name: str,
    confidence: float,
    hitl_active: bool,
    hitl_env: bool | None = None,
) -> tuple[bool, str, str | None, bool]:
    """Trả về ``(can_autopilot, status_init, review_notes, requires_conf)``.

    * Khi ``SAFETY_HITL_ENABLED=false`` (``hitl_env=False``) và ``hitl_active=False``:
      chạy **Full Autopilot** (dùng cho thực nghiệm M1/M2/M3) — cho phép mọi tool (cả Tier-2)
      tự động thực thi xuống Edge mà không bị chặn bởi ``TIER2_CRITICAL_TOOLS`` hay ngưỡng confidence.
    * Khi ``SAFETY_HITL_ENABLED=true`` (mặc định):
      - Nếu ``hitl_active=True``: bắt buộc duyệt tay (``pending``).
      - Nếu ``hitl_active=False`` (bật Autopilot trên UI): áp dụng **Tiered Autonomy** — chỉ tự động
        duyệt Tier-1 khi ``confidence >= 0.8``, chặn Tier-2 đẩy về ``pending``.
    """
    if hitl_env is None:
        hitl_env = hitl_env_enabled()

    tool_clean = str(tool_name or "").strip()
    tool_lower = tool_clean.lower()
    conf = float(confidence or 0.0)

    if hitl_active:
        return False, "pending", None, True

    # Full Autopilot mode khi tắt SAFETY_HITL_ENABLED trong .env (cấu hình M1, M2, M3)
    if not hitl_env:
        notes = (
            f"⚡ Tự động phê duyệt qua Full Autopilot "
            f"(SAFETY_HITL_ENABLED=false, Tool: {tool_clean}, Conf: {conf:.2f})"
        )
        return True, "auto_approved", notes, False

    is_critical = tool_lower in TIER2_CRITICAL_TOOLS
    has_min_conf = conf >= AUTOPILOT_MIN_CONFIDENCE

    if is_critical:
        notes = (
            f"🔒 [CHẶN AUTOPILOT]: Tool '{tool_clean}' là hành động nhạy cảm an ninh (Cửa/FSM), "
            "bắt buộc Quản trị viên duyệt qua HITL."
        )
        logger.warning(
            "🚨 [TIERED AUTONOMY] Chặn Autopilot đối với tool nhạy cảm: '%s'. Buộc chuyển sang HITL approval.",
            tool_clean,
        )
        return False, "pending", notes, True

    if not has_min_conf:
        notes = (
            f"⚠️ [CHẶN AUTOPILOT]: Độ tin cậy AI ({conf:.2f}) chưa đạt ngưỡng an toàn "
            f"({AUTOPILOT_MIN_CONFIDENCE}), cần con người xác nhận."
        )
        logger.info(
            "ℹ️ [TIERED AUTONOMY] Tool '%s' có confidence %.2f < %.2f. Chuyển sang HITL approval.",
            tool_clean,
            conf,
            AUTOPILOT_MIN_CONFIDENCE,
        )
        return False, "pending", notes, True

    notes = (
        f"⚡ Tự động phê duyệt qua Autopilot "
        f"(Tier-1 Reversible Tool, Conf: {conf:.2f} >= {AUTOPILOT_MIN_CONFIDENCE})"
    )
    return True, "auto_approved", notes, False
