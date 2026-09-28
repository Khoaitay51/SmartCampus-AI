"""Helpers for agent isolation testing.

Các helper này tập trung vào 3 lớp đánh giá cô lập:
1. Retrieval Isolation: kiểm tra retriever tìm đúng chunks liên quan.
2. Tool Selection Isolation: kiểm tra LLM sinh ra tool call hợp lệ trước khi thực thi.
3. Prompt & Reasoning Isolation: kiểm tra suy luận tiếp theo với context giả.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable, Mapping


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def compute_retrieval_metrics(
    relevant_docs_by_query: Mapping[str, Iterable[str]] | list[dict[str, Any]],
    retrieved_docs_by_query: Mapping[str, Iterable[str]],
    *,
    k: int = 3,
) -> dict[str, Any]:
    """Tính Hit Rate, MRR và Precision@k cho các query.

    Dữ liệu đầu vào có thể là:
    - dict(query -> list[relevant_docs])
    - list[{'query': ..., 'relevant_docs': [...], 'retrieved_docs': [...]}]
    """
    if isinstance(relevant_docs_by_query, list):
        parsed: dict[str, list[str]] = {}
        for item in relevant_docs_by_query:
            query = str(item.get("query") or item.get("question") or "")
            parsed[query] = list(item.get("relevant_docs") or item.get("relevant") or [])
        relevant_docs_by_query = parsed

    query_names = list(relevant_docs_by_query.keys())
    if not query_names:
        return {
            "hit_rate": 0.0,
            "mrr": 0.0,
            "precision_at_k": 0.0,
            "per_query": {},
        }

    hit_scores: list[float] = []
    mrr_scores: list[float] = []
    precision_scores: list[float] = []
    per_query: dict[str, dict[str, float]] = {}

    for query in query_names:
        relevant = [str(x) for x in (relevant_docs_by_query.get(query) or [])]
        retrieved = [str(x) for x in (retrieved_docs_by_query.get(query) or [])]
        top_k = retrieved[:k]
        rel_norm = {_normalize_text(doc) for doc in relevant}

        hit = 1.0 if any(_normalize_text(doc) in rel_norm for doc in top_k) else 0.0
        hit_scores.append(hit)

        mrr = 0.0
        for index, doc in enumerate(top_k, start=1):
            if _normalize_text(doc) in rel_norm:
                mrr = 1.0 / index
                break
        mrr_scores.append(mrr)

        precision = 0.0
        if top_k:
            precision = sum(1 for doc in top_k if _normalize_text(doc) in rel_norm) / len(top_k)
        precision_scores.append(precision)

        per_query[query] = {
            "hit_rate": hit,
            "mrr": mrr,
            "precision_at_k": precision,
        }

    return {
        "hit_rate": sum(hit_scores) / len(hit_scores),
        "mrr": sum(mrr_scores) / len(mrr_scores),
        "precision_at_k": sum(precision_scores) / len(precision_scores),
        "per_query": per_query,
    }


def _extract_tool_call_obj(raw_output: str | Mapping[str, Any]) -> tuple[str | None, dict[str, Any], list[str]]:
    """Trích xuất `tool_name` và `arguments` từ output JSON hoặc định dạng ReAct.

    Hỗ trợ các dạng:
    - {"tool": "get_telemetry", "arguments": {"room_id": "room-1"}}
    - {"tool_name": "get_telemetry", "parameters": {"room_id": "room-1"}}
    - Action: get_telemetry\nAction Input: {...}
    - Tool Call: get_telemetry\nTool Input: {...}
    """
    errors: list[str] = []
    if isinstance(raw_output, Mapping):
        payload = dict(raw_output)
        tool_name = (
            payload.get("tool_name")
            or payload.get("tool")
            or payload.get("action")
            or payload.get("name")
        )
        arguments = payload.get("arguments") or payload.get("parameters") or payload.get("action_input") or {}
        if not isinstance(arguments, dict):
            arguments = {}
            errors.append("arguments không phải dict")
        return str(tool_name) if tool_name is not None else None, arguments, errors

    text = str(raw_output).strip()
    try:
        payload = json.loads(text)
        return _extract_tool_call_obj(payload)
    except json.JSONDecodeError:
        pass

    match = re.search(r"(?:Action|Tool Call)\s*:\s*(?P<tool>[A-Za-z0-9_\-]+)", text, flags=re.IGNORECASE)
    tool_name = match.group("tool") if match else None
    args_match = re.search(r"(?:Action Input|Tool Input)\s*:\s*(?P<json>\{.*\})\s*$", text, flags=re.DOTALL)
    arguments: dict[str, Any] = {}
    if args_match:
        try:
            arguments = json.loads(args_match.group("json"))
        except json.JSONDecodeError:
            errors.append("Action Input không phải JSON hợp lệ")
    elif tool_name is not None:
        errors.append("thiếu Action Input / Tool Input JSON")

    return tool_name, arguments if isinstance(arguments, dict) else {}, errors


def validate_tool_selection(
    llm_tool_call: str | Mapping[str, Any],
    available_tools: Iterable[str],
    *,
    required_arguments: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Kiểm tra tool call hợp lệ trước khi thực thi.

    Trả về dict có trường valid, tool_name, arguments, errors.
    """
    tool_names = {str(name) for name in available_tools}
    tool_name, arguments, errors = _extract_tool_call_obj(llm_tool_call)

    if tool_name is None:
        return {
            "valid": False,
            "tool_name": None,
            "arguments": {},
            "errors": ["không phát hiện được tool name"] + errors,
        }

    normalized_name = str(tool_name).strip()
    if normalized_name not in tool_names:
        errors.append(f"tool '{normalized_name}' không nằm trong danh sách đã cho")

    if required_arguments:
        for key, expected in required_arguments.items():
            actual = arguments.get(key)
            if actual != expected:
                errors.append(f"tham số '{key}' phải là {expected!r}, nhận được {actual!r}")

    return {
        "valid": not errors,
        "tool_name": normalized_name,
        "arguments": arguments,
        "errors": errors,
    }


def validate_reasoning_step(
    observation: Mapping[str, Any] | str,
    thought: str,
    *,
    required_facts: Iterable[str],
    expected_action: str | None = None,
) -> dict[str, Any]:
    """Kiểm tra suy luận tiếp theo với fake context/fake observation.

    Dùng để đánh giá agent đang suy luận đúng theo dữ liệu đầu vào cố định.
    """
    text = _normalize_text(thought)
    observation_text = _normalize_text(json.dumps(observation, ensure_ascii=False, sort_keys=True)) if not isinstance(observation, str) else _normalize_text(observation)

    missing: list[str] = []
    for fact in required_facts:
        normalized_fact = _normalize_text(fact)
        if not normalized_fact or normalized_fact in text:
            continue
        if normalized_fact not in observation_text:
            missing.append(str(fact))

    if expected_action is not None:
        action_name = _normalize_text(expected_action)
        if action_name and action_name not in text:
            missing.append(f"expected action: {expected_action}")

    return {
        "valid": not missing,
        "missing_facts": missing,
    }
