"""
fallback/parsing.py
-------------------
CẤP 3 — Parsing Fallback cho đầu ra recommendation của LLM.

  Bước 0: trích JSON object từ text (bỏ ```fence```, cân ngoặc, sửa dấu phẩy thừa)
  Bước 1: nếu vẫn sai -> đưa lỗi ngược lại cho LLM nhờ sửa (tối đa max_repairs lần)
  Bước 2: nếu vẫn sai -> dùng regex cạo tool_name / confidence / ... ra khỏi văn bản

Dữ liệu cạo bằng regex kém tin cậy nên confidence bị chặn trên (SCRAPED_CONFIDENCE_CAP)
để lớp Final Safety Check không tự động execute.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

from .trace import LEVEL_PARSING, record

logger = logging.getLogger("agent.fallback.parsing")

KNOWN_TOOLS = {"set_fan", "set_door", "set_mode", "trigger_buzzer", "send_alert", "set_led"}
VALID_URGENCY = {"low", "medium", "high"}
SCRAPED_CONFIDENCE_CAP = 0.6


class SupportsComplete(Protocol):
    async def complete(self, system_prompt: str) -> str: ...


class ParsingExhausted(ValueError):
    """Đã thử trích xuất, sửa và cạo regex nhưng không lấy được recommendation hợp lệ."""


@dataclass
class ParseOutcome:
    data: dict[str, Any]
    method: str      # "direct" | "repaired" | "scraped"
    attempts: int = 0


# ---------------------------------------------------------------- trích JSON

def _strip_fences(text: str) -> str:
    return re.sub(r"```(?:json|JSON)?", "", text)


def _balanced_slice(text: str, start: int) -> str | None:
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None  # ngoặc không cân (JSON bị cắt cụt)


def _try_load(candidate: str) -> Any:
    for text in (candidate, re.sub(r",\s*([}\]])", r"\1", candidate)):
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            continue
    return None


def extract_json_object(text: str) -> dict[str, Any] | None:
    text = _strip_fences(text or "")
    start = text.find("{")
    while start != -1:
        candidate = _balanced_slice(text, start)
        if candidate:
            obj = _try_load(candidate)
            if isinstance(obj, dict):
                return obj
        start = text.find("{", start + 1)
    return None


# ---------------------------------------------------------------- validate

def validate_recommendation(obj: dict[str, Any], default_room_id: str | None = None) -> dict[str, Any]:
    """Chuẩn hoá về dạng ToolCall hoặc {"skip": True, ...}. Raise ValueError nếu sai."""
    if isinstance(obj.get("recommendation"), dict):
        obj = obj["recommendation"]
    if obj.get("skip") is True:
        return {"skip": True, "skip_reason": str(obj.get("skip_reason") or "unspecified")}

    tool = obj.get("tool_name")
    if tool not in KNOWN_TOOLS:
        raise ValueError(f"tool_name không hợp lệ: {tool!r} (cho phép: {sorted(KNOWN_TOOLS)})")
    params = obj.get("tool_params", {})
    if not isinstance(params, dict):
        raise ValueError("tool_params phải là object")
    reason = str(obj.get("reason") or "").strip()
    if not reason:
        raise ValueError("thiếu reason")
    conf = float(obj.get("confidence"))  # ValueError/TypeError nếu thiếu hoặc sai
    if not 0.0 <= conf <= 1.0:
        raise ValueError(f"confidence phải trong [0,1], nhận {conf}")
    urgency = obj.get("urgency")
    if urgency is not None and urgency not in VALID_URGENCY:
        raise ValueError(f"urgency không hợp lệ: {urgency!r}")

    params = dict(params)
    if default_room_id:
        params.setdefault("room_id", default_room_id)
    return {"tool_name": tool, "tool_params": params, "reason": reason, "confidence": conf, "urgency": urgency}


# ---------------------------------------------------------------- regex scrape

_RE_TOOL = re.compile(r'"?tool_name"?\s*[:=]\s*"?([a-z_]+)"?', re.I)
_RE_CONF = re.compile(r'"?confidence"?\s*[:=]\s*"?([0-9]*\.?[0-9]+)', re.I)
_RE_URG = re.compile(r'"?urgency"?\s*[:=]\s*"?(low|medium|high)"?', re.I)
_RE_REASON = re.compile(r'"?reason"?\s*[:=]\s*"((?:[^"\\]|\\.)*)"', re.I | re.S)


def scrape_recommendation(text: str, default_room_id: str | None = None) -> dict[str, Any] | None:
    text = text or ""
    m = _RE_TOOL.search(text)
    if not m or m.group(1).lower() not in KNOWN_TOOLS:
        return None

    params: dict[str, Any] = {}
    idx = text.find("tool_params")
    if idx != -1:
        brace = text.find("{", idx)
        if brace != -1:
            piece = _balanced_slice(text, brace)
            loaded = _try_load(piece) if piece else None
            if isinstance(loaded, dict):
                params = loaded
    if default_room_id:
        params.setdefault("room_id", default_room_id)

    conf = 0.5
    cm = _RE_CONF.search(text)
    if cm:
        try:
            conf = float(cm.group(1))
        except ValueError:
            pass
    conf = max(0.0, min(conf, SCRAPED_CONFIDENCE_CAP))

    um = _RE_URG.search(text)
    rm = _RE_REASON.search(text)
    return {
        "tool_name": m.group(1).lower(),
        "tool_params": params,
        "reason": (rm.group(1) if rm else "Trích xuất bằng regex từ đầu ra LLM sai định dạng").strip(),
        "confidence": conf,
        "urgency": um.group(1).lower() if um else None,
    }


# ---------------------------------------------------------------- orchestration

def _repair_prompt(bad_output: str, error: str) -> str:
    return (
        "Bạn là bộ sửa lỗi JSON. Đầu ra trước đó của bạn KHÔNG hợp lệ.\n"
        f"Lỗi: {error}\n\nĐầu ra cần sửa:\n<<<\n{bad_output[:4000]}\n>>>\n\n"
        "Hãy trả về DUY NHẤT 1 JSON object hợp lệ với các khóa: "
        f"tool_name (một trong {sorted(KNOWN_TOOLS)}), tool_params (object), reason (string), "
        'confidence (số 0..1), urgency ("low"|"medium"|"high").\n'
        'Nếu không có hành động nào: {"skip": true, "skip_reason": "..."}.\n'
        "Không markdown, không giải thích."
    )


async def parse_recommendation(
    raw: str, llm: SupportsComplete | None, *, max_repairs: int = 3, default_room_id: str | None = None,
) -> ParseOutcome:
    """Trả ParseOutcome hoặc raise ParsingExhausted."""
    text = raw
    error = "không tìm thấy JSON object"

    for attempt in range(max_repairs + 1):
        obj = extract_json_object(text)
        try:
            if obj is None:
                raise ValueError("không tìm thấy JSON object hợp lệ trong đầu ra")
            data = validate_recommendation(obj, default_room_id)
            if attempt > 0:
                record(LEVEL_PARSING, f"LLM sửa JSON thành công sau {attempt} lần", "parsing")
            return ParseOutcome(data, "direct" if attempt == 0 else "repaired", attempt)
        except (ValueError, TypeError) as exc:
            error = str(exc)
            logger.warning("Parse recommendation lỗi (lần %d): %s", attempt + 1, error)

        if attempt == max_repairs or llm is None:
            break
        try:
            text = await llm.complete(_repair_prompt(text, error))
        except Exception as exc:  # noqa: BLE001 - LLM chết thì chuyển sang regex
            logger.warning("Không nhờ LLM sửa JSON được: %s", exc)
            break

    for candidate in (text, raw):
        scraped = scrape_recommendation(candidate, default_room_id)
        if scraped:
            record(LEVEL_PARSING, f"phải cạo regex (confidence bị chặn ≤ {SCRAPED_CONFIDENCE_CAP}); lỗi cuối: {error}", "parsing")
            return ParseOutcome(scraped, "scraped", max_repairs)

    record(LEVEL_PARSING, f"không parse được recommendation: {error}", "parsing")
    raise ParsingExhausted(error)
