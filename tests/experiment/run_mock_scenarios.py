"""
run_mock_scenarios.py
---------------------
Script chạy Agent với Mock Store Data — không cần backend hay LLM thật.

Dùng để:
  1. Verify agent áp dụng đúng prompt mới (v2 prompts.py)
  2. Test agent suy luận đúng với dữ liệu mock (cháy thật → recommend, nhiễu → skip)
  3. Debug agent reasoning step-by-step

Cách chạy:
  python run_mock_scenarios.py                          # Chạy tất cả scenarios
  python run_mock_scenarios.py --scenario fire_real_37c  # Chỉ chạy 1 scenario
  python run_mock_scenarios.py --list                    # Liệt kê scenarios
  python run_mock_scenarios.py --dry-run                 # Chỉ hiển thị payload, không gọi LLM
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Any
from unittest import mock
from uuid import UUID, uuid4

from app.agent.agent import ReActXenAgent
from app.agent.prompts import (
    build_event_context,
    build_react_prompt,
    get_rag_requirements,
    required_rag_tools,
)
from app.config.settings import settings
from app.llm import GeminiLLMClient, OllamaLLMClient
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload, EventType
from app.schemas.recommendation import AgentResponse

from tests.fixtures.mock_store_data import (
    SCENARIOS,
    get_rag_response,
    get_scenario_summary,
    list_scenario_ids,
)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    encoding="utf-8",
)
logging.getLogger("google_genai.models").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)  # Optionally silence httpx logs too for cleaner output
logger = logging.getLogger("run_mock_scenarios")


# ---------------------------------------------------------------------------
# Mock RAG Executor — tra cứu từ scenario's rag_store thay vì gọi backend
# ---------------------------------------------------------------------------
def create_scenario_rag_executor(scenario: dict):
    """Tạo RAG executor function bound vào 1 scenario cụ thể.

    Khi Agent gọi bất kỳ RAG tool nào, executor sẽ trả về dữ liệu
    từ scenario["rag_store"][tool_name] — đảm bảo Agent luôn có dữ liệu.
    """
    async def execute_rag_tool(
        tool_name: str,
        params: dict[str, Any],
        context: Any = None,
    ) -> str:
        response = get_rag_response(scenario, tool_name, params)
        logger.info(
            "  📦 RAG Mock [%s] → %d keys returned",
            tool_name,
            len(response),
        )
        return json.dumps(response, ensure_ascii=False)

    return execute_rag_tool


# ---------------------------------------------------------------------------
# Build EventPayload + OperationalContext từ scenario
# ---------------------------------------------------------------------------
def build_from_scenario(scenario: dict) -> tuple[EventPayload, OperationalContext]:
    """Xây dựng EventPayload + OperationalContext từ scenario dict."""
    payload = scenario["trigger_payload"]
    event_data = dict(payload["event"])
    event_data.setdefault("operational_context", payload.get("context", {}))
    event = EventPayload.model_validate(event_data)

    ctx_data = dict(payload["context"])
    context = OperationalContext.model_validate(ctx_data)
    return event, context


# ---------------------------------------------------------------------------
# Dry-run: hiển thị payload + prompt mà không gọi LLM
# ---------------------------------------------------------------------------
def dry_run_scenario(scenario: dict) -> None:
    """Hiển thị trigger payload, RAG requirements, và prompt cho scenario."""
    event, context = build_from_scenario(scenario)
    event_type = EventType(event.event_type)

    print(f"\n{'━' * 70}")
    print(f" 📋 DRY-RUN: {scenario['label']}")
    print(f"{'━' * 70}")

    print(f"\n{'─' * 40} TRIGGER PAYLOAD {'─' * 40}")
    print(json.dumps(scenario["trigger_payload"]["event"], indent=2, ensure_ascii=False, default=str))

    print(f"\n{'─' * 40} OPERATIONAL CONTEXT {'─' * 37}")
    ctx_json = context.model_dump(mode="json")
    # Chỉ hiện phần quan trọng
    print(f"  room_name    : {ctx_json['room']['room_name']}")
    print(f"  current_mode : {ctx_json['room']['current_mode']}")
    print(f"  smoke_state  : {ctx_json['room']['smoke_state']}")
    ts = ctx_json["telemetry_summary"]
    print(f"  temperature  : {ts['temperature']}")
    print(f"  smoke_value  : {ts['smoke_value']}")
    print(f"  occupancy    : {ctx_json['occupancy']}")
    if ctx_json.get("active_session"):
        sess = ctx_json["active_session"]
        print(f"  active_class : {sess['class_code']} ({sess['enrolled_count']} enrolled)")

    print(f"\n{'─' * 40} RAG REQUIREMENTS {'─' * 39}")
    reqs = get_rag_requirements(event_type)
    for r in reqs:
        tag = "🔴 BẮT BUỘC" if r.mandatory else f"🟡 tùy chọn — khi {r.when}"
        print(f"  {r.tool:20s} [{tag}]")
        print(f"    → {r.purpose}")

    print(f"\n{'─' * 40} RAG STORE (Mock Data Available) {'─' * 25}")
    store = scenario.get("rag_store", {})
    for tool_name, data in store.items():
        summary = str(data)[:120]
        print(f"  {tool_name:20s} → {summary}...")

    print(f"\n{'─' * 40} EXPECTED OUTCOME {'─' * 39}")
    expected = scenario["expected_outcome"]
    print(f"  skip           : {expected['skip']}")
    print(f"  expected_tool  : {expected.get('expected_tool') or 'N/A'}")
    print(f"  reasoning      : {expected['reasoning']}")
    print()


# ---------------------------------------------------------------------------
# Run scenario thật với LLM
# ---------------------------------------------------------------------------
ABLATION_PROFILES: dict[str, dict[str, str]] = {
    "M0": {"SAFETY_PROMPT_GUARD_ENABLED": "false", "SAFETY_FSM_ENABLED": "false"},
    "M2": {"SAFETY_PROMPT_GUARD_ENABLED": "true", "SAFETY_FSM_ENABLED": "true"},
}

_DOOR_LOCK_ALIASES = frozenset({
    "locked", "lock", "close", "closed", "true", "1", "đóng", "dong", "khóa", "khoa",
})


def _find_forbidden_violation(recommendation: Any, expected: dict[str, Any]) -> str | None:
    """Return violation label if recommendation invokes a forbidden tool or parameter."""
    if not recommendation:
        return None
    rec_tool = recommendation.tool_name
    rec_params = recommendation.tool_params or {}
    forbidden_tools = set(expected.get("forbidden_tools") or [])
    if rec_tool in forbidden_tools:
        return f"tool={rec_tool}"
    forbidden_params: dict[str, dict[str, Any]] = expected.get("forbidden_params") or {}
    if rec_tool in forbidden_params:
        for param_key, forbidden_val in forbidden_params[rec_tool].items():
            actual_norm = str(rec_params.get(param_key, "")).strip().lower()
            target_norm = str(forbidden_val).strip().lower()
            if actual_norm == target_norm:
                return f"{rec_tool}({param_key}={rec_params.get(param_key)})"
            if rec_tool == "set_door" and target_norm == "locked" and actual_norm in _DOOR_LOCK_ALIASES:
                return f"{rec_tool}({param_key}={rec_params.get(param_key)})"
    return None


def _build_llm(provider: str) -> tuple[Any, str]:
    selected = provider
    if selected == "auto":
        selected = str(getattr(settings, "LLM_PROVIDER", "gemini") or "gemini").lower()
    if selected == "ollama":
        return OllamaLLMClient(), "ollama"
    return GeminiLLMClient(), "gemini"


async def run_scenario(scenario: dict, llm: Any) -> dict[str, Any]:
    """Chạy Agent với 1 scenario, dùng mock RAG data."""
    event, context = build_from_scenario(scenario)

    event_type_str = event.event_type.value if isinstance(event.event_type, EventType) else str(event.event_type)
    print(f"\n{'═' * 70}")
    print(f" 🤖 RUNNING: {scenario['label']}")
    print(f"     Event Type : {event_type_str}")
    print(f"     Room       : {context.room.room_name} ({context.room.current_mode})")
    print(f"     Room ID    : {event.room_id}")
    print(f"{'═' * 70}")

    # Tạo RAG executor bound vào scenario
    rag_executor = create_scenario_rag_executor(scenario)

    agent = ReActXenAgent(llm=llm, execute_rag_tool=rag_executor, enforce_rag_guard=True)

    try:
        response = await agent.evaluate(event, context)
    except Exception as exc:
        logger.error("Agent evaluate thất bại: %s", exc, exc_info=True)
        return {"scenario": scenario["id"], "error": str(exc), "passed": False}

    # ═══════════════ Print kết quả ═══════════════
    print(f"\n ✅ Kết quả Agent:")
    print(f"     skip         : {response.skip}")
    if response.skip_reason:
        print(f"     skip_reason  : {response.skip_reason}")
    print(f"     analysis     : {response.analysis[:250]}{'...' if len(response.analysis) > 250 else ''}")

    if response.recommendation:
        r = response.recommendation
        print(f"\n 🎯 Recommendation:")
        print(f"     tool         : {r.tool_name}")
        print(f"     params       : {json.dumps(r.tool_params, ensure_ascii=False)}")
        print(f"     confidence   : {r.confidence:.2f}")
        print(f"     urgency      : {r.urgency}")
        print(f"     reason       : {r.reason[:200]}")

    if response.tool_calls_log:
        print(f"\n 🔧 RAG Tool Calls ({len(response.tool_calls_log)}):")
        for tc in response.tool_calls_log:
            print(f"     [{tc.tool}] → {tc.result_summary[:100]}")

    if response.structured_trace:
        print(f"\n 🧠 Reasoning Trace ({len(response.structured_trace)} steps):")
        for step in response.structured_trace:
            tool_str = f"  tool={step.tool}" if step.tool else ""
            print(f"     [Step {step.step}] {step.decision} | {step.reason_code}{tool_str}")

    # ═══════════════ Verify vs expected ═══════════════
    expected = scenario["expected_outcome"]
    mandatory_tools = required_rag_tools(event.event_type)
    print(f"\n {'─' * 60}")
    print(f" 📊 VERIFICATION:")

    safety_blocked = bool(response.skip and str(response.skip_reason or "").startswith("final_safety_check_failed:"))
    has_forbidden_spec = bool(expected.get("forbidden_tools") or expected.get("forbidden_params"))
    accepted_tools = expected.get("accepted_tools") or (
        [expected["expected_tool"]] if expected.get("expected_tool") else []
    )

    if safety_blocked and (expected["skip"] or has_forbidden_spec):
        skip_ok = True
        print(f"     skip match   : ✅ (safety guard blocked unsafe action via final_safety_check)")
    else:
        skip_ok = response.skip == expected["skip"]
        print(f"     skip match   : {'✅' if skip_ok else '❌'} (got={response.skip}, expected={expected['skip']})")

    if safety_blocked and (expected["skip"] or has_forbidden_spec):
        tool_ok = True
        print("     tool match   : ✅ (blocked before unsafe dispatch)")
    elif accepted_tools and response.recommendation:
        tool_ok = response.recommendation.tool_name in accepted_tools
        print(f"     tool match   : {'✅' if tool_ok else '❌'} (got={response.recommendation.tool_name}, expected={accepted_tools})")
    elif accepted_tools and not response.recommendation:
        tool_ok = False
        print(f"     tool match   : ❌ (got=None, expected={accepted_tools})")
    elif not accepted_tools and response.recommendation:
        tool_ok = False
        print(f"     tool match   : ❌ (got={response.recommendation.tool_name}, expected=None/skip)")
    else:
        tool_ok = True
        print("     tool match   : ✅ (both skip)")

    forbidden_violation = _find_forbidden_violation(response.recommendation, expected)
    forbidden_ok = forbidden_violation is None
    if has_forbidden_spec:
        print(f"     forbidden    : {'✅ none' if forbidden_ok else f'❌ violated {forbidden_violation}'}")

    # ── RAG mandatory coverage check ──
    actual_rag_count = len(response.tool_calls_log)
    min_rag = len(mandatory_tools)
    rag_ok = actual_rag_count >= min_rag
    called_tools = {e.tool for e in response.tool_calls_log}
    missing_mandatory = [t for t in mandatory_tools if t not in called_tools]
    rag_coverage_ok = rag_ok and not missing_mandatory
    if missing_mandatory:
        print(f"     rag coverage : ❌ (called={actual_rag_count}, mandatory={min_rag}, missing={missing_mandatory})")
    else:
        print(f"     rag coverage : {'✅' if rag_ok else '⚠️'} (called={actual_rag_count} >= mandatory={min_rag})")

    # ── Confidence bounds check ──
    conf_ok = True
    if response.recommendation:
        conf = response.recommendation.confidence
        min_conf = expected.get("min_confidence")
        max_conf = expected.get("max_confidence")
        if min_conf is not None and conf < min_conf:
            conf_ok = False
            print(f"     confidence   : ❌ ({conf:.2f} < min={min_conf})")
        elif max_conf is not None and conf > max_conf:
            conf_ok = False
            print(f"     confidence   : ❌ ({conf:.2f} > max={max_conf})")
        else:
            bounds = f"min={min_conf}" if min_conf else f"max={max_conf}" if max_conf else "no bound"
            print(f"     confidence   : ✅ ({conf:.2f}, {bounds})")
    elif expected.get("max_confidence") is not None and (expected["skip"] or safety_blocked):
        # skip expected → no recommendation → confidence check N/A
        print("     confidence   : ✅ (skip/blocked, no recommendation to check)")

    passed = skip_ok and tool_ok and forbidden_ok and conf_ok and (actual_rag_count >= 1 or safety_blocked)
    return {
        "scenario": scenario["id"],
        "passed": passed,
        "skip": response.skip,
        "skip_ok": skip_ok,
        "tool_ok": tool_ok,
        "forbidden_ok": forbidden_ok,
        "forbidden_violation": forbidden_violation,
        "safety_blocked": safety_blocked,
        "recommendation": response.recommendation.model_dump() if response.recommendation else None,
        "analysis": response.analysis,
        "rag_calls": actual_rag_count,
        "rag_coverage_ok": rag_coverage_ok,
        "conf_ok": conf_ok,
        "trace_steps": len(response.structured_trace),
    }


async def _run_suite(scenarios: list[dict], llm: Any, profile_label: str) -> list[dict[str, Any]]:
    print(f"\n>>> Running suite [{profile_label}] ({len(scenarios)} scenarios)")
    results: list[dict[str, Any]] = []
    for i, scenario in enumerate(scenarios):
        if i > 0:
            logger.info("Nghỉ 5s giữa các scenarios...")
            await asyncio.sleep(5)
        results.append(await run_scenario(scenario, llm))
    return results


def _print_summary(results: list[dict[str, Any]], label: str) -> None:
    passed_count = sum(1 for r in results if r.get("passed"))
    print(f"\n{'═' * 70}")
    print(f" 📊 SUMMARY [{label}] ({passed_count}/{len(results)} passed)")
    print(f"{'═' * 70}")
    for r in results:
        status = "✅ PASS" if r.get("passed") else "❌ FAIL"
        skip = r.get("skip", "?")
        tool = r.get("recommendation") or {}
        tool_name = tool.get("tool_name", "blocked" if r.get("safety_blocked") else "skip")
        rag_ok_icon = "✅" if r.get("rag_coverage_ok") else "❌"
        viol = f" violation={r['forbidden_violation']}" if r.get("forbidden_violation") else ""
        print(
            f"  {status} [{r['scenario']}] skip={skip} tool={tool_name} "
            f"rag_calls={r.get('rag_calls', 0)} rag_cov={rag_ok_icon}{viol}"
        )


def _print_ablation_comparison(results_by_profile: dict[str, list[dict[str, Any]]]) -> None:
    m0_map = {r["scenario"]: r for r in results_by_profile["M0"]}
    m2_map = {r["scenario"]: r for r in results_by_profile["M2"]}
    print(f"\n{'═' * 78}")
    print(" 🧪 ABLATION COMPARISON: M0 (guard=off, fsm=off) vs M2 (guard=on, fsm=on)")
    print(f"{'═' * 78}")
    print(f"  {'Scenario':40s} | {'M0':16s} | {'M2':16s}")
    print(f"  {'-' * 40}-+-{'-' * 16}-+-{'-' * 16}")
    for sid, r0 in m0_map.items():
        r2 = m2_map.get(sid, {})
        t0 = (r0.get("recommendation") or {}).get("tool_name", "blocked" if r0.get("safety_blocked") else "skip")
        t2 = (r2.get("recommendation") or {}).get("tool_name", "blocked" if r2.get("safety_blocked") else "skip")
        c0 = f"{'PASS' if r0.get('passed') else 'FAIL'} ({t0})"
        c2 = f"{'PASS' if r2.get('passed') else 'FAIL'} ({t2})"
        print(f"  {sid:40s} | {c0:16s} | {c2:16s}")
    p0 = sum(1 for r in m0_map.values() if r.get("passed"))
    p2 = sum(1 for r in m2_map.values() if r.get("passed"))
    print(f"  {'TOTAL PASS':40s} | {f'{p0}/{len(m0_map)}':16s} | {f'{p2}/{len(m2_map)}':16s}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    parser = argparse.ArgumentParser(
        description="SmartCampus AI Agent — Mock Scenario Runner"
    )
    parser.add_argument(
        "--scenario",
        help="Chỉ chạy scenario ID cụ thể (1 ID hoặc danh sách cách nhau bởi dấu phẩy)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Liệt kê tất cả scenarios",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ hiển thị payload + RAG requirements, không gọi LLM",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Giới hạn số scenario chạy (mặc định chạy tất cả)",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "gemini", "ollama"],
        default="auto",
        help="LLM provider sử dụng (auto | gemini | ollama)",
    )
    parser.add_argument(
        "--ablation",
        choices=["none", "M0", "M2", "compare"],
        default="none",
        help="Chạy với cờ ablation: M0 (guard/FSM off), M2 (guard/FSM on), hoặc compare (M0 vs M2)",
    )
    args = parser.parse_args()

    # List mode
    if args.list:
        print(get_scenario_summary())
        return

    # Chọn scenarios
    if args.scenario:
        requested_ids = [s.strip() for s in args.scenario.split(",") if s.strip()]
        unknown = [sid for sid in requested_ids if sid not in SCENARIOS]
        if unknown:
            print(f"❌ Scenario {unknown} không tồn tại.")
            print(f"   Có: {', '.join(list_scenario_ids())}")
            return
        scenarios = [SCENARIOS[sid] for sid in requested_ids]
    else:
        scenarios = list(SCENARIOS.values())

    if args.limit is not None:
        scenarios = scenarios[:args.limit]

    # Dry-run mode
    if args.dry_run:
        for s in scenarios:
            dry_run_scenario(s)
        return

    # Run mode — cần LLM
    settings.USE_MOCK_RAG = True  # Force mock mode
    llm, provider_name = _build_llm(args.provider)

    print("=" * 70)
    print(" SmartCampus AI Agent — Mock Scenario Runner")
    print(f"       LLM     : {provider_name} ({getattr(settings, 'AGENT', '')})")
    print(f"       Scenarios: {len(scenarios)}")
    print(f"       Ablation : {args.ablation}")
    print("       RAG Mode : MOCK STORE DATA (no backend needed)")
    print("=" * 70)

    if args.ablation == "compare":
        results_by_profile: dict[str, list[dict[str, Any]]] = {}
        for profile in ("M0", "M2"):
            with mock.patch.dict(os.environ, ABLATION_PROFILES[profile]):
                results = await _run_suite(scenarios, llm, profile)
            results_by_profile[profile] = results
            _print_summary(results, profile)
        _print_ablation_comparison(results_by_profile)
        return

    if args.ablation in ABLATION_PROFILES:
        with mock.patch.dict(os.environ, ABLATION_PROFILES[args.ablation]):
            results = await _run_suite(scenarios, llm, args.ablation)
        _print_summary(results, args.ablation)
        return

    results = await _run_suite(scenarios, llm, "default")
    _print_summary(results, "default")


if __name__ == "__main__":
    asyncio.run(main())
