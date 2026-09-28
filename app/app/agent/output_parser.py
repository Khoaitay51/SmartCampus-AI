from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.schemas.recommendation import AgentResponse

# ---------------------------------------------------------------------------
# Regex chính — khớp cả 2 format: "Action/Action Input" (ReAct chuẩn) và
# "Tool Call/Tool Input" (format prompts.py OUTPUT_FORMAT_INSTRUCTIONS).
# ---------------------------------------------------------------------------
_STEP_RE = re.compile(
    r"(?:Self-Ask:\s*(?P<self_ask>.*?)\n)?"
    r"(?:Thought|Think):\s*(?P<thought>.*?)\n"
    r"(?:Action|Tool Call):\s*(?P<action>.*?)\n"
    r"(?:Action Input|Tool Input):\s*(?P<action_input>\{.*?\})\s*(?:\n|$)",
    re.DOTALL,
)


def _normalize_react_output(text: str) -> str:
    """Soft-repair: cố normalise text trước khi đưa vào regex chính.

    Xử lý các biến thể phổ biến mà model hay trả:
    - Strip ``` markdown fences bao quanh toàn bộ output
    - Chuẩn hoá field thừa xuống dòng (JSON nhiều dòng trong Action Input)
    Không thay đổi ngữ nghĩa; chỉ căn chỉnh whitespace & label.
    """
    # Strip code fences toàn bộ nếu có
    text = re.sub(r"^```(?:json|text|)?\n?", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\n?```$", "", text.strip(), flags=re.MULTILINE)
    return text


class OutputParseError(Exception):
    pass


@dataclass
class ParsedReactStep:
    self_ask: str | None
    thought: str
    action: str
    action_input: dict


def _repair_json(raw: str) -> str:
    """Cố sửa JSON bị cắt cụt hoặc thừa dấu phẩy cuối cùng."""
    raw = raw.strip()
    # Bỏ trailing comma trước } hoặc ]
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    # Nếu không cân ngoặc, thêm } đóng
    if raw.count("{") > raw.count("}"):
        raw += "}" * (raw.count("{") - raw.count("}"))
    return raw


def parse_react_step(raw_text: str) -> ParsedReactStep:
    """Parse ReAct step với soft-repair: normalize trước, retry sau khi repair JSON."""
    normalized = _normalize_react_output(raw_text)

    # Thử parse text đã normalize
    for candidate in (normalized, raw_text):
        match = _STEP_RE.search(candidate)
        if not match:
            continue

        action = match.group("action").strip().strip('"')
        raw_input = match.group("action_input")

        # Thử parse JSON trực tiếp, fallback sang repair
        action_input: dict | None = None
        for json_candidate in (raw_input, _repair_json(raw_input)):
            try:
                action_input = json.loads(json_candidate)
                break
            except json.JSONDecodeError:
                continue

        if action_input is None:
            raise OutputParseError(f"Action Input không phải JSON hợp lệ sau khi repair: {raw_input[:200]}")

        return ParsedReactStep(
            self_ask=(match.group("self_ask") or "").strip() or None,
            thought=match.group("thought").strip(),
            action=action,
            action_input=action_input,
        )

    raise OutputParseError(f"Không parse được ReAct step từ output:\n{raw_text[:500]}")


@dataclass
class ReviewResult:
    status: str  # "Accomplished" | "Partially Accomplished" | "Not Accomplished"
    reasoning: str
    suggestions: str | None


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def parse_review_output(raw_text: str) -> ReviewResult:
    try:
        data = json.loads(_strip_code_fence(raw_text))
    except json.JSONDecodeError as e:
        raise OutputParseError(f"Review output không phải JSON hợp lệ: {e}") from e

    status = data.get("status")
    if status not in {"Accomplished", "Partially Accomplished", "Not Accomplished"}:
        raise OutputParseError(f"Review status không hợp lệ: {status!r}")

    return ReviewResult(
        status=status,
        reasoning=data.get("reasoning", ""),
        suggestions=data.get("suggestions"),
    )


def parse_final_recommendation(action_input: dict, event_id) -> AgentResponse:
    final_json = action_input.get("final_json")
    if final_json is None:
        raise OutputParseError("Action Input của 'finish' thiếu field 'final_json'")

    final_json = dict(final_json)
    final_json["event_id"] = str(event_id)
    final_json.setdefault("tool_calls_log", [])
    final_json.setdefault("alternatives", [])
    final_json.setdefault("skip", False)

    try:
        return AgentResponse.model_validate(final_json)
    except Exception as e:  # pydantic.ValidationError
        raise OutputParseError(f"final_json không đúng schema AgentResponse: {e}") from e