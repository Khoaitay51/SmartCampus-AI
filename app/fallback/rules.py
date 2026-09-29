"""
fallback/rules.py
-----------------
CẤP 4 — Rule-based Fallback: chốt chặn cuối khi LLM (cả Google lẫn local) đều chết
hoặc agent bị crash. Không gọi mạng, không gọi LLM, chỉ dùng dữ liệu trong event.

Bám 5 kịch bản trong AI_AGENT_SCENARIO_GUIDE.md. Quy tắc an toàn tính mạng
(khói) luôn được kiểm tra TRƯỚC, bất kể loại event.

Mọi đề xuất đều đi qua ma trận quyền theo chế độ phòng (is_tool_allowed_in_mode).
Đây là bản sao cục bộ để module chạy độc lập; nếu dự án đã có hàm thật trong safety/,
hãy truyền vào tham số `is_allowed` của evaluate_by_rules() để dùng bản chính thức.

Đường dẫn đọc dữ liệu từ event (xem _extract_facts) là GIẢ ĐỊNH theo guide,
hãy chỉnh cho khớp payload thật của Gateway.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .trace import LEVEL_RULES, record

SMOKE_THRESHOLD = 400
TEMP_THRESHOLD = 32.0
CO2_THRESHOLD = 1000
HIGH_TEMP = 35.0
EMPTY_SECONDS = 900  # 15 phút

KNOWN_MODES = {"SAVING", "SELF_STUDY", "LECTURE", "EXAM", "LOCK", "SUSPECTED", "EMERGENCY"}

# Cột "No" trong ma trận quyền (guide, mục 3)
_DENIED: dict[str, set[str]] = {
    "EXAM": {"set_door", "trigger_buzzer"},
    "LOCK": {"set_fan", "set_door", "set_led"},
    "SUSPECTED": {"set_led"},
    "EMERGENCY": {"set_led"},
}
_ALWAYS_SAFE_UNKNOWN_MODE = {"send_alert"}


def is_tool_allowed_in_mode(mode: str | None, tool_name: str) -> bool:
    mode = (mode or "").upper()
    if mode not in KNOWN_MODES:
        # Không biết phòng đang ở chế độ nào (có thể là EXAM) => chỉ cho phép gửi cảnh báo
        return tool_name in _ALWAYS_SAFE_UNKNOWN_MODE
    return tool_name not in _DENIED.get(mode, set())


@dataclass
class Facts:
    event_type: str
    event_id: str
    room_id: str | None
    mode: str
    smoke_state: str | None
    smoke_value: float | None
    temperature: float | None
    co2: float | None
    occupancy: int | None
    has_active_session: bool | None
    empty_seconds: float | None


@dataclass
class Candidate:
    tool_name: str
    tool_params: dict[str, Any]
    reason: str
    confidence: float
    urgency: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"tool_name": self.tool_name, "tool_params": self.tool_params, "reason": self.reason,
                "confidence": self.confidence, "urgency": self.urgency}


def _get(d: Any, *paths: str, default: Any = None) -> Any:
    for path in paths:
        cur = d
        for key in path.split("."):
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                cur = None
                break
        if cur is not None:
            return cur
    return default


def _num(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _extract_facts(event: dict[str, Any]) -> Facts:
    ctx = event.get("operational_context") or {}
    tele = "operational_context.latest_telemetry"
    tsum = "operational_context.telemetry_summary"
    occ = _num(_get(event, "event_data.current_count", "payload.current_count", "payload.occupancy", "operational_context.occupancy.current_count"))
    return Facts(
        event_type=str(event.get("event_type") or event.get("type") or ""),
        event_id=str(event.get("event_id") or event.get("id") or "unknown"),
        room_id=_get(event, "room_id", "payload.room_id", "operational_context.room.id", "operational_context.room_id"),
        mode=str(_get(event, "operational_context.room.state", "operational_context.room.mode", "operational_context.room.current_mode",
                      "operational_context.fsm_state", "operational_context.current_state",
                      "payload.room_state", "room_state", default="")).upper(),
        smoke_state=(str(_get(event, "event_data.smoke_state", "payload.smoke_state", f"{tele}.smoke_state", f"{tsum}.smoke_state", default="")).lower() or None),
        smoke_value=_num(_get(event, "event_data.smoke_value", "payload.smoke_value", "payload.smoke", f"{tele}.smoke", f"{tsum}.smoke_value.latest")),
        temperature=_num(_get(event, "event_data.temperature", "payload.temperature", f"{tele}.temperature", f"{tsum}.temperature.latest")),
        co2=_num(_get(event, "event_data.co2", "payload.co2", f"{tele}.co2", f"{tsum}.co2.latest")),
        occupancy=int(occ) if occ is not None else None,
        has_active_session=bool(ctx["active_session"]) if "active_session" in ctx and ctx["active_session"] is not None else None,
        empty_seconds=_num(_get(event, "payload.empty_for_seconds", "operational_context.occupancy.empty_for_seconds")),
    )


# ------------------------------------------------------------------ rules

def _rule_smoke(f: Facts) -> list[Candidate]:
    triggered = f.smoke_state == "suspected" or (f.smoke_value is not None and f.smoke_value > SMOKE_THRESHOLD)
    if not triggered:
        return []
    detail = f"smoke_state={f.smoke_state or 'n/a'}, smoke_value={f.smoke_value}"
    r = f.room_id
    return [
        Candidate("trigger_buzzer", {"room_id": r, "pattern": "emergency"},
                  f"Rule: phát hiện khói ({detail}) — bật còi khẩn cấp.", 0.9, "high"),
        Candidate("set_mode", {"room_id": r, "mode": "EMERGENCY"},
                  f"Rule: phát hiện khói ({detail}) — chuyển phòng sang EMERGENCY.", 0.85, "high"),
        Candidate("set_door", {"room_id": r, "state": "unlocked"},
                  f"Rule: phát hiện khói ({detail}) — mở khóa cửa để sơ tán.", 0.85, "high"),
        Candidate("send_alert", {"room_id": r, "level": "critical", "message": f"Nghi cháy tại phòng {r}: {detail}"},
                  f"Rule: phát hiện khói ({detail}) — báo ban quản lý.", 0.9, "high"),
    ]


def _rule_temperature(f: Facts) -> list[Candidate]:
    hot = f.temperature is not None and f.temperature > TEMP_THRESHOLD
    stuffy = f.co2 is not None and f.co2 > CO2_THRESHOLD
    if not (hot or stuffy):
        return []
    if f.occupancy == 0:
        return []  # phòng trống: không tốn điện làm mát
    detail = f"temperature={f.temperature}, co2={f.co2}, occupancy={f.occupancy}"
    urgent = f.temperature is not None and f.temperature >= HIGH_TEMP
    r = f.room_id
    return [
        Candidate("set_fan", {"room_id": r, "state": "on"}, f"Rule: môi trường vượt ngưỡng ({detail}) — bật quạt.",
                  0.8, "high" if urgent else "medium"),
        Candidate("send_alert", {"room_id": r, "level": "warning",
                                 "message": f"Phòng {r} nóng/ngột ngạt ({detail}). Mở cửa sổ, kiểm tra điều hòa."},
                  f"Rule: nhắc kiểm tra thông gió ({detail}).", 0.75, "medium"),
    ]


def _rule_occupancy(f: Facts) -> list[Candidate]:
    if f.occupancy != 0 or f.has_active_session is True:
        return []
    if f.empty_seconds is not None and f.empty_seconds < EMPTY_SECONDS:
        return []
    known = f.empty_seconds is not None
    detail = f"occupancy=0, empty_for={f.empty_seconds if known else 'n/a'}s, active_session={f.has_active_session}"
    conf = 0.8 if known else 0.7  # chưa biết phòng trống bao lâu => tin cậy thấp hơn
    r = f.room_id
    return [
        Candidate("set_fan", {"room_id": r, "state": "off"}, f"Rule: phòng trống ({detail}) — tắt quạt tiết kiệm điện.", conf, "low"),
        Candidate("set_mode", {"room_id": r, "mode": "SAVING"}, f"Rule: phòng trống ({detail}) — chuyển SAVING.", conf, "low"),
    ]


def _rule_rfid(f: Facts) -> list[Candidate]:
    r = f.room_id
    sensitive = f.mode in ("EXAM", "LOCK")
    detail = f"thẻ RFID lạ, phòng ở chế độ {f.mode or 'không rõ'}"
    cands = [Candidate("send_alert",
                       {"room_id": r, "level": "warning", "message": f"Cảnh báo an ninh phòng {r}: {detail}"},
                       f"Rule: {detail} — báo bảo vệ/giảng viên trực.", 0.85 if sensitive else 0.7, "medium")]
    cands.append(Candidate("trigger_buzzer", {"room_id": r, "pattern": "short"},
                           f"Rule: {detail} — bíp cảnh báo tại chỗ.", 0.7, "medium"))
    return cands


_EVENT_RULES: dict[str, list[Callable[[Facts], list[Candidate]]]] = {
    "smoke_detected": [],
    "temperature_anomaly": [_rule_temperature],
    "occupancy_change": [_rule_occupancy],
    "rfid_unknown": [_rule_rfid],
    "manual_trigger": [_rule_temperature],
}


# ------------------------------------------------------------------ public API

def evaluate_by_rules(
    event: dict[str, Any],
    *,
    is_allowed: Callable[[str | None, str], bool] = is_tool_allowed_in_mode,
    reason: str = "",
) -> dict[str, Any]:
    """Trả dict đúng dạng RecommendationPayload (+ tool_calls_log đánh dấu fallback)."""
    f = _extract_facts(event)
    record(LEVEL_RULES, f"dùng rule-based cho event '{f.event_type}'" + (f": {reason}" if reason else ""), "rules")

    rules = [_rule_smoke] + _EVENT_RULES.get(f.event_type, [])  # an toàn tính mạng luôn đi trước
    candidates: list[Candidate] = []
    for rule in rules:
        candidates.extend(rule(f))

    allowed = [c for c in candidates if is_allowed(f.mode, c.tool_name)]
    blocked = [c.tool_name for c in candidates if not is_allowed(f.mode, c.tool_name)]

    prefix = "[FALLBACK: rules] "
    # Audit entries này đi vào fallback_audit_log, KHÔNG phải tool_calls_log
    audit = [{"tool": "fallback", "level": LEVEL_RULES, "detail": reason or "rule-based evaluation"}]
    base = {"event_id": f.event_id, "alternatives": [], "tool_calls_log": [], "fallback_audit_log": audit}

    if not candidates:
        skip_reason = "all_metrics_normal" if f.event_type == "manual_trigger" else "no_rule_matched"
        return {**base, "recommendation": None, "skip": True, "skip_reason": skip_reason,
                "analysis": prefix + f"Không quy tắc nào kích hoạt (mode={f.mode or 'n/a'}); giữ nguyên trạng thái."}

    if not allowed:
        return {**base, "recommendation": None, "skip": True, "skip_reason": "all_candidate_tools_blocked_by_mode",
                "analysis": prefix + f"Các hành động {blocked} đều bị cấm ở chế độ {f.mode or 'không rõ'}."}

    note = f" Đã loại {blocked} do ma trận quyền chế độ {f.mode or 'không rõ'}." if blocked else ""
    return {
        **base,
        "recommendation": allowed[0].to_dict(),
        "alternatives": [c.to_dict() for c in allowed[1:]],
        "skip": False,
        "skip_reason": None,
        "analysis": prefix + f"AI/LLM không khả dụng, áp dụng quy tắc cứng. {allowed[0].reason}{note}",
    }
