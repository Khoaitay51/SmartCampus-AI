import argparse
import asyncio
import json
import logging
from typing import Any
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent.agent import ReActXenAgent
from app.config.settings import settings
from app.gateway.llm_client import LLMClient
from app.gateway.rag import execute_rag_tool
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_rag_tests")

async def run_scenario(scenario: dict[str, Any], llm: LLMClient) -> bool:
    print(f"\n{'=' * 70}")
    print(f"Running Scenario: {scenario['name']}")
    print(f"Description: {scenario['description']}")
    print(f"{'=' * 70}")

    payload = scenario["payload"]
    expected = scenario["expected_behavior"]
    mock_responses = scenario.get("mock_tool_responses", {})

    event = EventPayload.model_validate(payload)
    
    context = OperationalContext.model_validate(payload["operational_context"])

    async def custom_execute_rag_tool(tool_name: str, params: dict[str, Any], ctx: Any = None, client: Any = None) -> str:
        if tool_name in mock_responses:
            data = mock_responses[tool_name]
            logger.info(f"MOCK RAG STORE: Trả về data cho {tool_name}")
            return json.dumps(data, ensure_ascii=False)
        else:
            logger.warning(f"MOCK RAG STORE: Thiếu data cho {tool_name}, trả về rỗng")
            return json.dumps({"status": "no_mock_data_for_this_tool"})

    agent = ReActXenAgent(llm=llm, execute_rag_tool=custom_execute_rag_tool)

    try:
        response = await agent.evaluate(event, context)
    except Exception as exc:
        logger.error(f"Agent evaluate failed: {exc}")
        return False

    actual_rag_tools = [tc.tool for tc in response.tool_calls_log] if response.tool_calls_log else []
    actual_action = response.recommendation.tool_name if response.recommendation else None

    passed = True
    
    required_rag_tools = expected.get("required_rag_tools", [])
    missing_rag_tools = [t for t in required_rag_tools if t not in actual_rag_tools]
    if missing_rag_tools:
        print(f"❌ FAILED: Missing required RAG tools: {missing_rag_tools}. Actual: {actual_rag_tools}")
        passed = False
    else:
        print(f"✅ PASSED: Called required RAG tools: {required_rag_tools}")

    recommended_action = expected.get("recommended_action")
    if recommended_action:
        actual_action_str = str(actual_action) if actual_action is not None else "None"
        if actual_action_str == recommended_action:
            print(f"✅ PASSED: Recommended action is '{actual_action_str}'")
        else:
            print(f"❌ FAILED: Expected action '{recommended_action}', but got '{actual_action_str}'")
            passed = False

    print(f"\n--- Agent Analysis ---")
    print(f"{response.analysis}")
    if response.recommendation:
        print(f"--- Agent Recommendation Reason ---")
        print(f"{response.recommendation.reason}")
        print(f"--- Agent Tool Params ---")
        print(f"{response.recommendation.tool_params}")

    return passed

async def main():
    parser = argparse.ArgumentParser(description="Run RAG specific test cases")
    parser.add_argument("--mock", action="store_true", help="Bật chế độ Mock RAG data")
    args = parser.parse_args()

    if args.mock:
        settings.USE_MOCK_RAG = True

    fixture_path = Path("tests/fixtures/test_cases_rag_challenging_1_4.json")
    if not fixture_path.exists():
        logger.error(f"File not found: {fixture_path}")
        return

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenarios = data.get("scenarios", [])
    if not scenarios:
        logger.error("No scenarios found in fixture.")
        return

    llm = LLMClient(model="gemini-3.5-flash-lite")
    total = len(scenarios)
    passed = 0

    print(f"Starting execution of {total} challenging RAG test cases with Gemini 3.5 Flash Lite...\n")

    for idx, scenario in enumerate(scenarios):
        if idx > 0:
            print("\nSleeping 8s to avoid rate limits...")
            await asyncio.sleep(8)
            
        success = await run_scenario(scenario, llm)
        if success:
            passed += 1

    print(f"\n{'=' * 70}")
    print(f"Test Summary: {passed}/{total} passed.")
    print(f"{'=' * 70}")

if __name__ == "__main__":
    asyncio.run(main())
