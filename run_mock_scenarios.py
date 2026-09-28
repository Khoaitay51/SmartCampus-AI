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
import sys
from typing import Any
from uuid import UUID, uuid4

from app.agent.agent import ReActXenAgent
from app.agent.prompts import (
    build_event_context,
    build_react_prompt,
    get_rag_requirements,
    required_rag_tools,
)
from app.config.settings import settings
from app.gateway.llm_client import LLMClient
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
)
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
async def run_scenario(scenario: dict, llm: LLMClient) -> dict[str, Any]:
    """Chạy Agent với 1 scenario, dùng mock RAG data."""
    event, context = build_from_scenario(scenario)

    print(f"\n{'═' * 70}")
    print(f" 🤖 RUNNING: {scenario['label']}")
    print(f"     Event Type : {event.event_type.value}")
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
        return {"scenario": scenario["id"], "error": str(exc)}

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
    skip_ok = response.skip == expected["skip"]
    print(f"     skip match   : {'✅' if skip_ok else '❌'} (got={response.skip}, expected={expected['skip']})")

    if expected.get("expected_tool") and response.recommendation:
        tool_ok = response.recommendation.tool_name == expected["expected_tool"]
        print(f"     tool match   : {'✅' if tool_ok else '❌'} (got={response.recommendation.tool_name}, expected={expected['expected_tool']})")
    elif expected.get("expected_tool") and not response.recommendation:
        print(f"     tool match   : ❌ (got=None, expected={expected['expected_tool']})")
    elif not expected.get("expected_tool") and response.recommendation:
        print(f"     tool match   : ❌ (got={response.recommendation.tool_name}, expected=None/skip)")
    else:
        print(f"     tool match   : ✅ (both skip)")

    # ── RAG mandatory coverage check ──
    actual_rag_count = len(response.tool_calls_log)
    min_rag = len(mandatory_tools)
    rag_ok = actual_rag_count >= min_rag
    called_tools = {e.tool for e in response.tool_calls_log}
    missing_mandatory = [t for t in mandatory_tools if t not in called_tools]
    if missing_mandatory:
        print(f"     rag coverage : ❌ (called={actual_rag_count}, mandatory={min_rag}, missing={missing_mandatory})")
    else:
        print(f"     rag coverage : {'✅' if rag_ok else '⚠️'} (called={actual_rag_count} >= mandatory={min_rag})")

    # ── Confidence bounds check ──
    if response.recommendation:
        conf = response.recommendation.confidence
        min_conf = expected.get("min_confidence")
        max_conf = expected.get("max_confidence")
        if min_conf is not None and conf < min_conf:
            print(f"     confidence   : ❌ ({conf:.2f} < min={min_conf})")
        elif max_conf is not None and conf > max_conf:
            print(f"     confidence   : ❌ ({conf:.2f} > max={max_conf})")
        else:
            bounds = f"min={min_conf}" if min_conf else f"max={max_conf}" if max_conf else "no bound"
            print(f"     confidence   : ✅ ({conf:.2f}, {bounds})")
    elif expected.get("max_confidence") is not None and expected["skip"]:
        # skip expected → no recommendation → confidence check N/A
        print(f"     confidence   : ✅ (skip, no recommendation to check)")

    return {
        "scenario": scenario["id"],
        "skip": response.skip,
        "recommendation": response.recommendation.model_dump() if response.recommendation else None,
        "analysis": response.analysis,
        "rag_calls": actual_rag_count,
        "rag_coverage_ok": rag_ok and not missing_mandatory,
        "trace_steps": len(response.structured_trace),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    parser = argparse.ArgumentParser(
        description="SmartCampus AI Agent — Mock Scenario Runner"
    )
    parser.add_argument(
        "--scenario",
        help="Chỉ chạy scenario ID cụ thể (ví dụ: fire_real_37c)",
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
    args = parser.parse_args()

    # List mode
    if args.list:
        print(get_scenario_summary())
        return

    # Chọn scenarios
    if args.scenario:
        if args.scenario not in SCENARIOS:
            print(f"❌ Scenario '{args.scenario}' không tồn tại.")
            print(f"   Có: {', '.join(list_scenario_ids())}")
            return
        scenarios = [SCENARIOS[args.scenario]]
    else:
        scenarios = list(SCENARIOS.values())

    # Dry-run mode
    if args.dry_run:
        for s in scenarios:
            dry_run_scenario(s)
        return

    # Run mode — cần LLM
    print("=" * 70)
    print(" SmartCampus AI Agent — Mock Scenario Runner")
    print(f"       LLM     : {settings.AGENT}")
    print(f"       Scenarios: {len(scenarios)}")
    print(f"       RAG Mode : MOCK STORE DATA (no backend needed)")
    print("=" * 70)

    settings.USE_MOCK_RAG = True  # Force mock mode
    llm = LLMClient()

    results = []
    for i, scenario in enumerate(scenarios):
        if i > 0:
            logger.info("Nghỉ 5s giữa các scenarios...")
            await asyncio.sleep(5)

        result = await run_scenario(scenario, llm)
        results.append(result)

    # Summary
    print(f"\n{'═' * 70}")
    print(f" 📊 SUMMARY ({len(results)} scenarios)")
    print(f"{'═' * 70}")
    for r in results:
        status = "✅" if not r.get("error") else "❌"
        skip = r.get("skip", "?")
        tool = r.get("recommendation", {})
        tool_name = tool.get("tool_name", "skip") if tool else "skip"
        rag_ok_icon = "✅" if r.get("rag_coverage_ok") else "❌"
        print(f"  {status} [{r['scenario']}] skip={skip} tool={tool_name} rag_calls={r.get('rag_calls', 0)} rag_cov={rag_ok_icon}")


if __name__ == "__main__":
    asyncio.run(main())
