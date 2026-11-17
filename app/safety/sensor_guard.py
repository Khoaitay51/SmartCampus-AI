"""
app/safety/sensor_guard.py
-------------------------
Lớp phòng thủ deterministic đặt SAU agent, TRƯỚC Policy Engine / thực thi (đề xuất D1 + D2).

Nguyên tắc: trạng thái cảm biến có cấu trúc (operational_context, số đo trong event_data) là nguồn sự thật.
Free-text (event_data.description) chỉ được bổ sung ngữ cảnh, KHÔNG được làm giảm phản ứng
với một nguy cơ mà cảm biến đã đo được. Guard không đọc description, nên kẻ tấn công không tác động được.

  D2 Veto: chặn hành động mâu thuẫn trực tiếp với cảm biến (tắt quạt khi quá nhiệt / CO2 cao,
           chuyển SAVING khi có nguy cơ, khóa cửa khi có khói/ngạt và có người, mở cửa khi thẻ bị từ chối,
           hú còi liên tục / EMERGENCY khi không có bằng chứng khói).
  D1 Floor: nếu cảm biến vượt ngưỡng nguy hiểm mà đầu ra của agent không phải hành động bảo vệ
           (skip, alert info / không có level, set_led, hoặc hành động vừa bị veto)
           -> phát hành động bảo vệ tối thiểu `send_alert` (warning / critical). Alert không điều khiển
           thiết bị, nên không vượt quyền tiered autonomy.

Không gọi thêm LLM, không gọi thêm tool: chi phí ~0 ms, không ảnh hưởng budget của agent.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Ngưỡng nguy hiểm (chỉ dựa trên cảm biến).
# Nguồn ngưỡng:
#   - Nhiệt: 38 °C nằm trong dải "quá nhiệt nghiêm trọng 35–40 °C" của
#     campus_knowledge/sop_02_temperature_hvac_control.md (SOP: > 40 °C là nguy hiểm).
#     TEMP_CRITICAL = 43 chưa có trong SOP (chọn tay).
#   - CO2 (1500 ppm) và khói (200 / 400 ppm): CHỌN TAY, chưa có nguồn SOP/datasheet (tra "ppm" trong
#     campus_knowledge chưa thấy). Cần bổ sung nguồn hoặc quét độ nhạy ngưỡng (xem reports).
# Lưu ý: ngưỡng CO2/khói được đặt giữa mức Anomaly và Hazard của bộ benign (xem ghi chú từng dòng),
# nên khi báo cáo phải nêu rõ điều này và có thêm ca giữ riêng.
TEMP_HAZARD = 38.0        # °C (trong dải SOP_02: 35–40)
TEMP_CRITICAL = 43.0
CO2_HAZARD = 1500.0       # ppm, benign Anomaly 1200–1440, Hazard từ 1650
SMOKE_HAZARD = 200.0      # ppm, benign Anomaly ~12, Hazard từ 220
SMOKE_CRITICAL = 400.0
# Ngưỡng "không còn bình thường" dùng cho veto tắt quạt / SAVING
TEMP_ELEVATED, CO2_ELEVATED, SMOKE_ELEVATED = 35.0, 1000.0, 100.0

ACTION_TOOLS = {"set_fan", "set_door", "set_mode", "trigger_buzzer", "send_alert", "set_led"}
ALERT_OK = {"warning", "critical", "high"}


def _latest(oc: Dict[str, Any], key: str) -> Optional[float]:
    v = ((oc.get("telemetry_summary") or {}).get(key) or {}).get("latest")
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _num(d: Dict[str, Any], *keys: str) -> Optional[float]:
    for k in keys:
        if d.get(k) is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                pass
    return None


def read_sensors(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Chỉ đọc trường có cấu trúc. Bỏ qua hoàn toàn event_data.description."""
    oc = payload.get("operational_context") or {}
    ev = payload.get("event") or {}
    ed = {k: v for k, v in (ev.get("event_data") or {}).items() if k != "description"}
    room = oc.get("room") or {}
    temp = max(x for x in (_latest(oc, "temperature"), _num(ed, "temperature"), -1e9) if x is not None)
    co2 = max(x for x in (_latest(oc, "co2"), _num(ed, "co2_level", "co2"), -1e9) if x is not None)
    smoke = max(x for x in (_latest(oc, "smoke_value"), _num(ed, "smoke_level", "smoke_value", "smoke"), -1e9) if x is not None)
    occ = (oc.get("occupancy") or {}).get("current_count") or _num(ed, "occupancy") or 0
    smoke_state = str(room.get("smoke_state") or "").upper()
    access = str(ed.get("access_result") or "").upper()
    if not access and ed.get("access_granted") is False:
        access = "DENIED"
    if ed.get("intrusion_confirmed") is True:
        access = "DENIED_INTRUSION"
    rfid_events = sum(1 for e in (oc.get("recent_events") or [])
                      if any(w in str(e.get("type", "")).lower() for w in ("rfid", "unauthorized", "intrusion")))
    return dict(temp=temp, co2=co2, smoke=smoke, occ=float(occ), smoke_state=smoke_state,
                mode=str(room.get("current_mode") or "").upper(), access=access, rfid_events=rfid_events,
                event_type=str(ev.get("event_type") or ""))


def hazards(s: Dict[str, Any]) -> Dict[str, bool]:
    smoke_real = s["smoke_state"] in ("DETECTED", "EMERGENCY") or s["smoke"] >= SMOKE_HAZARD
    return {
        "smoke": smoke_real,
        "temp": s["temp"] >= TEMP_HAZARD,
        "co2": s["co2"] >= CO2_HAZARD and s["occ"] > 0,
        "rfid": s["access"].startswith("DENIED") and (s["mode"] == "LOCK" or s["rfid_events"] >= 1),
    }


def _protective(step: Dict[str, Any], hz: Dict[str, bool]) -> bool:
    t, p = step.get("tool"), step.get("params") or {}
    if t == "send_alert":
        return str(p.get("level") or p.get("severity") or "").lower() in ALERT_OK
    if t == "set_fan" and str(p.get("state", "")).lower() in ("on", "1", "true", "high", "bật"):
        return hz["temp"] or hz["co2"] or hz["smoke"]
    if t == "trigger_buzzer":
        return hz["smoke"] or hz["rfid"]
    if t == "set_mode":
        m = str(p.get("mode", "")).upper()
        return (m == "EMERGENCY" and hz["smoke"]) or (m in ("LOCK", "SUSPECTED") and hz["rfid"])
    if t == "set_door" and str(p.get("state", "")).lower() in ("unlocked", "open"):
        return hz["smoke"] or hz["co2"]          # mở đường thoát
    return False


def veto_reason(step: Dict[str, Any], s: Dict[str, Any], hz: Dict[str, bool]) -> Optional[str]:
    t, p = step.get("tool"), step.get("params") or {}
    state = str(p.get("state", "")).lower()
    mode = str(p.get("mode", "")).upper()
    elevated = s["temp"] >= TEMP_ELEVATED or s["co2"] >= CO2_ELEVATED or s["smoke"] >= SMOKE_ELEVATED
    smoke_evidence = s["smoke_state"] in ("DETECTED", "EMERGENCY") or s["smoke"] >= SMOKE_CRITICAL
    if t == "set_fan" and state in ("off", "0", "false", "stop", "tắt") and elevated:
        return "tắt quạt khi cảm biến đang ở mức cao"
    if t == "set_mode" and mode in ("SAVING", "SELF_STUDY") and (elevated or any(hz.values())):
        return f"chuyển {mode} khi đang có nguy cơ"
    if t == "set_door" and state in ("locked", "lock", "close", "closed", "khóa") and (hz["smoke"] or hz["co2"]) and s["occ"] > 0:
        return "khóa cửa khi có khói/ngạt và có người"
    if t == "set_door" and state in ("unlocked", "unlock", "open", "opened", "mở") and s["access"].startswith("DENIED"):
        return "mở cửa khi thẻ vừa bị từ chối"
    if t == "trigger_buzzer" and str(p.get("pattern", "")).lower() in ("continuous", "long") and not smoke_evidence and not hz["rfid"]:
        return "hú còi dài/liên tục khi không có bằng chứng khói"
    if t == "set_mode" and mode == "EMERGENCY" and not smoke_evidence:
        return "EMERGENCY khi không có bằng chứng khói"
    if t == "set_mode" and mode == "LOCK" and (hz["smoke"] or hz["co2"]) and s["occ"] > 0:
        return "LOCK khi có khói/ngạt và có người"
    return None


def floor_action(room_id: Optional[str], s: Dict[str, Any], hz: Dict[str, bool]) -> Dict[str, Any]:
    critical = (hz["smoke"] and (s["occ"] > 0 or s["smoke_state"] == "EMERGENCY" or s["smoke"] >= SMOKE_CRITICAL)) \
        or s["temp"] >= TEMP_CRITICAL
    kinds = [k for k, v in hz.items() if v]
    return {"tool": "send_alert", "params": {"room_id": room_id, "level": "critical" if critical else "warning",
            "message": f"[SensorGuard] Cảm biến vượt ngưỡng ({', '.join(kinds)}); cần người phụ trách xác minh ngay."},
            "_guard": "floor"}


def apply(payload: Dict[str, Any], actions: List[Dict[str, Any]], veto: bool = True, floor: bool = True
          ) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Trả (danh sách hành động sau guard, nhật ký can thiệp)."""
    s = read_sensors(payload)
    hz = hazards(s)
    log, kept = [], []
    for a in actions:
        r = veto_reason(a, s, hz) if veto else None
        if r:
            log.append(f"veto {a.get('tool')}: {r}")
        else:
            kept.append(a)
    if floor and any(hz.values()) and not any(_protective(a, hz) for a in kept):
        room_id = (payload.get("event") or {}).get("room_id")
        kept = [a for a in kept if a.get("tool") != "send_alert"] + [floor_action(room_id, s, hz)]
        log.append(f"floor send_alert {kept[-1]['params']['level']} ({[k for k, v in hz.items() if v]})")
    return kept, log
