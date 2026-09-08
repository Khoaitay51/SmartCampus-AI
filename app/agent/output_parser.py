from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.schemas.recommendation import AgentResponse

_STEP_RE = re.compile(
    r"(?:Self-Ask:\s*(?P<self_ask>.*?)\n)?"
    r"Thought:\s*(?P<thought>.*?)\n"
    r"Action:\s*(?P<action>.*?)\n"
    r"Action Input:\s*(?P<action_input>\{.*?\})\s*(?:\n|$)",
    re.DOTALL,
)


class OutputParseError(Exception):
    pass


@dataclass
class ParsedReactStep:
    self_ask: str | None
    thought: str
    action: str
    action_input: dict


def parse_react_step(raw_text: str) -> ParsedReactStep:
    match = _STEP_RE.search(raw_text)
    if not match:
        raise OutputParseError(f"Không parse được ReAct step từ output:\n{raw_text[:500]}")

    action = match.group("action").strip().strip('"')
    try:
        action_input = json.loads(match.group("action_input"))
    except json.JSONDecodeError as e:
        raise OutputParseError(f"Action Input không phải JSON hợp lệ: {e}") from e

    return ParsedReactStep(
        self_ask=(match.group("self_ask") or "").strip() or None,
        thought=match.group("thought").strip(),
        action=action,
        action_input=action_input,
    )


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