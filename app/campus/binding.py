"""
app/campus/binding.py
---------------------
Ràng buộc bất biến giữa cái người duyệt nhìn thấy và cái được thực thi (Consent Integrity)
+ ràng buộc với trạng thái vật lý của phòng lúc đề xuất (chống physical TOCTOU).

* ``payload_hash``: SHA-256 của *canonical command* thực sự sẽ xuống Edge (đã dịch từ tool),
  không phải bản tóm tắt ngôn ngữ tự nhiên. Tính lại ở thời điểm duyệt và so sánh chính xác.
* ``expected_mode`` / ``expected_state_version``: trạng thái FSM của phòng lúc đề xuất. Edge Gateway
  sẽ từ chối (409) nếu trạng thái đã đổi.

Binding được lưu trong ``tool_params["_binding"]`` để không cần migration schema.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

BINDING_KEY = "_binding"


def strip_binding(tool_params: dict[str, Any] | None) -> dict[str, Any]:
    """Bản sao của tool_params không chứa metadata binding (dùng để hash/dịch lệnh)."""
    return {k: v for k, v in (tool_params or {}).items() if k != BINDING_KEY}


def canonical_payload(
    room_id: str | None,
    tool_name: str,
    tool_params: dict[str, Any] | None,
    command: tuple[str, str] | None,
) -> dict[str, Any]:
    """Payload kỹ thuật chuẩn hóa: đây là thứ UI phải hiển thị và là thứ được hash."""
    payload: dict[str, Any] = {
        "room_id": str(room_id or strip_binding(tool_params).get("room_id", "") or ""),
        "tool_name": (tool_name or "").lower().strip(),
        "command_type": command[0] if command else None,
        "command_value": command[1] if command else None,
    }
    if command is None:
        # Tool không có lệnh phần cứng (vd send_alert): bind cả tham số để không bị thay nội dung.
        payload["params"] = strip_binding(tool_params)
    return payload


def hash_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_payload_hash(
    room_id: str | None, tool_name: str, tool_params: dict[str, Any] | None
) -> tuple[str, dict[str, Any]]:
    """Trả về ``(hash, canonical_payload)`` cho một đề xuất."""
    from app.campus.command_translation import translate_recommendation_to_command

    params = strip_binding(tool_params)
    command = translate_recommendation_to_command(tool_name, params)
    payload = canonical_payload(room_id, tool_name, params, command)
    return hash_payload(payload), payload


def build_binding(
    room_id: str | None,
    tool_name: str,
    tool_params: dict[str, Any] | None,
    expected_mode: str | None,
    expected_state_version: str | None,
) -> dict[str, Any]:
    digest, _ = compute_payload_hash(room_id, tool_name, tool_params)
    return {
        "payload_hash": digest,
        "expected_mode": (expected_mode or None),
        "expected_state_version": expected_state_version,
    }


def with_binding(
    room_id: str | None,
    tool_name: str,
    tool_params: dict[str, Any] | None,
    expected_mode: str | None,
    expected_state_version: str | None,
) -> dict[str, Any]:
    """tool_params + ``_binding`` để lưu DB."""
    params = strip_binding(tool_params)
    params[BINDING_KEY] = build_binding(
        room_id, tool_name, params, expected_mode, expected_state_version
    )
    return params


def get_binding(tool_params: dict[str, Any] | None) -> dict[str, Any] | None:
    b = (tool_params or {}).get(BINDING_KEY)
    return b if isinstance(b, dict) else None


def verify_binding(
    room_id: str | None,
    tool_name: str,
    tool_params: dict[str, Any] | None,
    client_hash: str | None = None,
) -> tuple[bool, str]:
    """Kiểm tra payload hiện tại còn khớp với cái đã bind lúc đề xuất (và cái UI hiển thị).

    Trả về ``(ok, reason)``. Đề xuất cũ không có binding => ``(True, "legacy_unbound")``
    trừ khi client gửi hash (khi đó vẫn phải khớp với hash tính lại).
    Khi ``SAFETY_TOCTOU_BINDING_ENABLED=false`` => trả về ``(True, "toctou_binding_disabled")``.
    """
    from app.config.safety import toctou_binding_enabled

    if not toctou_binding_enabled():
        return True, "toctou_binding_disabled"

    binding = get_binding(tool_params)
    current_hash, _ = compute_payload_hash(room_id, tool_name, tool_params)

    if binding and binding.get("payload_hash") != current_hash:
        return False, "payload_mutated_after_proposal"
    if client_hash and client_hash != current_hash:
        return False, "payload_differs_from_what_operator_saw"
    if not binding:
        return True, "legacy_unbound"
    return True, "ok"
