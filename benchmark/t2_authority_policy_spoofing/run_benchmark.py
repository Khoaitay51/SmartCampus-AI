#!/usr/bin/env python3
"""
run_benchmark.py
----------------
Script tự động thực thi 12 testcase của Taxonomy T2 (Authority & Policy Spoofing)
và thu thập toàn bộ trace suy luận (ReAct Thought), công cụ đề xuất (Tool Call),
và mức độ khẩn cấp (Urgency) từ AI Agent.

Hỗ trợ 2 chế độ:
  1. REST API (mặc định): Gửi request tới AI Service đang chạy (http://localhost:8001/api/evaluate)
  2. Direct in-memory: Import trực tiếp ReActXenAgent trong Python để chạy độc lập.

Sử dụng:
  python run_benchmark.py
  python run_benchmark.py --mode direct
  python run_benchmark.py --testcase TC-T2-01
  python run_benchmark.py --api-url http://localhost:8001/api/evaluate
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any
import urllib.request
import urllib.error

# Thiết lập encoding cho console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("T2_Benchmark_Runner")

SCRIPT_DIR = Path(__file__).parent.resolve()
TESTCASES_FILE = SCRIPT_DIR / "testcases_t2.json"
RESULTS_DIR = SCRIPT_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Đảm bảo import được code dự án khi chạy chế độ direct
PROJECT_ROOT = SCRIPT_DIR.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def load_testcases() -> list[dict[str, Any]]:
    if not TESTCASES_FILE.exists():
        raise FileNotFoundError(f"Không tìm thấy file {TESTCASES_FILE}")
    with open(TESTCASES_FILE, "r", encoding="utf-8-sig") as f:
        return json.load(f)


async def execute_via_api(api_url: str, testcase: dict[str, Any], timeout: float = 120.0) -> dict[str, Any]:
    """Thực thi testcase qua REST API của AI Service."""
    payload = testcase["payload"]
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=data_bytes,
        headers={"Content-Type": "application/json", "User-Agent": "SmartCampus-T2-Benchmark/1.0"},
        method="POST",
    )

    start_time = time.perf_counter()
    loop = asyncio.get_running_loop()

    def _call():
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        response_json = await loop.run_in_executor(None, _call)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "success": True,
            "latency_ms": latency_ms,
            "response": response_json,
            "error": None,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        error_msg = str(exc)
        if isinstance(exc, urllib.error.HTTPError):
            try:
                error_body = exc.read().decode("utf-8")
                error_msg = f"HTTP {exc.code}: {error_body}"
            except Exception:
                pass
        return {
            "success": False,
            "latency_ms": latency_ms,
            "response": None,
            "error": error_msg,
        }


async def execute_via_direct_agent(testcase: dict[str, Any]) -> dict[str, Any]:
    """Thực thi testcase trực tiếp qua instance ReActXenAgent trong bộ nhớ."""
    from app.agent.agent import ReActXenAgent
    from app.llm import GeminiLLMClient, OllamaLLMClient
    from app.config.settings import settings
    from app.schemas.events import EventPayload
    from app.schemas.context import OperationalContext

    payload = testcase["payload"]
    event = EventPayload.model_validate(payload["event"])
    context = OperationalContext.model_validate(payload["operational_context"])
    event.operational_context = context.model_dump(mode="json")

    # Khởi tạo LLM Client theo cấu hình
    provider = getattr(settings, "LLM_PROVIDER", "gemini").lower()
    if provider == "ollama":
        llm = OllamaLLMClient()
    else:
        llm = GeminiLLMClient()

    # Mock RAG executor đơn giản cho benchmark
    async def mock_rag(tool_name: str, params: dict[str, Any], ctx: Any = None) -> str:
        return json.dumps({
            "status": "success",
            "message": f"Dữ liệu tra cứu cho {tool_name}",
            "params": params,
        }, ensure_ascii=False)

    agent = ReActXenAgent(llm=llm, execute_rag_tool=mock_rag, enforce_rag_guard=False)

    start_time = time.perf_counter()
    try:
        resp = await agent.evaluate(event)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "success": True,
            "latency_ms": latency_ms,
            "response": resp.model_dump(mode="json"),
            "error": None,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "success": False,
            "latency_ms": latency_ms,
            "response": None,
            "error": str(exc),
        }


async def run_benchmark(
    mode: str = "api",
    api_url: str = "http://localhost:8001/api/evaluate",
    filter_testcase: str | None = None,
    output_file: str | None = None,
) -> Path:
    testcases = load_testcases()
    if filter_testcase:
        testcases = [tc for tc in testcases if tc["testcase_id"] == filter_testcase or filter_testcase in tc["name"]]
        if not testcases:
            logger.error("Không tìm thấy testcase nào khớp với: %s", filter_testcase)
            sys.exit(1)

    logger.info("=" * 75)
    logger.info(" BẮT ĐẦU CHẠY BENCHMARK T2: AUTHORITY & POLICY SPOOFING")
    logger.info(" Chế độ: %s | Số lượng testcases: %d", mode.upper(), len(testcases))
    if mode == "api":
        logger.info(" API Target: %s", api_url)
    logger.info("=" * 75)

    run_results = []
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    for idx, tc in enumerate(testcases, start=1):
        tc_id = tc["testcase_id"]
        tc_name = tc["name"]
        group = tc["group"]
        logger.info("[%d/%d] Đang thực thi %s (%s)...", idx, len(testcases), tc_id, tc_name)

        if mode == "api":
            result = await execute_via_api(api_url, tc)
        else:
            result = await execute_via_direct_agent(tc)

        resp = result.get("response") or {}
        rec = resp.get("recommendation")
        tool_name = rec.get("tool_name") if rec else None
        urgency = rec.get("urgency") if rec else None

        if result["success"]:
            logger.info("  -> Thành công (%s ms): Tool=%s | Urgency=%s", result["latency_ms"], tool_name, urgency)
        else:
            logger.warning("  -> THẤT BẠI: %s", result["error"])

        record = {
            "testcase_id": tc_id,
            "name": tc_name,
            "group": group,
            "factors": tc["factors"],
            "oracle": tc["oracle"],
            "execution": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        run_results.append(record)
        # Giãn cách 2.0s để tránh nghẽn API quota
        await asyncio.sleep(2.0)

    # Lưu kết quả
    filename = output_file or f"run_t2_{run_timestamp}.json"
    target_path = RESULTS_DIR / filename
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(run_results, f, ensure_ascii=False, indent=2)

    # Cập nhật latest_run.json
    latest_path = RESULTS_DIR / "latest_run.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(run_results, f, ensure_ascii=False, indent=2)

    logger.info("=" * 75)
    logger.info(" HOÀN THÀNH BENCHMARK T2!")
    logger.info(" Kết quả lưu tại: %s", target_path)
    logger.info(" File mới nhất:   %s", latest_path)
    logger.info("=" * 75)
    return target_path


def main():
    parser = argparse.ArgumentParser(description="Chạy Benchmark T2 Authority & Policy Spoofing")
    parser.add_argument(
        "--mode",
        choices=["api", "direct"],
        default="api",
        help="Chế độ thực thi: 'api' (gọi FastAPI qua HTTP) hoặc 'direct' (chạy in-memory Python)",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8001/api/evaluate",
        help="URL endpoint evaluate của AI Service",
    )
    parser.add_argument(
        "--testcase",
        default=None,
        help="Mã hoặc tên testcase cụ thể cần chạy (ví dụ: TC-T2-01)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Tên file kết quả lưu trong thư mục results/",
    )
    args = parser.parse_args()

    asyncio.run(
        run_benchmark(
            mode=args.mode,
            api_url=args.api_url,
            filter_testcase=args.testcase,
            output_file=args.output,
        )
    )


if __name__ == "__main__":
    main()
