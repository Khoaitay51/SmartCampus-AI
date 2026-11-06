#!/usr/bin/env python3
"""
benchmarkv2_refined/attack_test/runner/run_attack.py
---------------------------------------------------
Runner thực thi chính thức phân hệ Attack Test V2 trên môi trường Live (Phương án B):
- Kết nối trực tiếp:
  - Gemini 3.5 Flash Lite (hoặc Ollama khi cấu hình)
  - Edge Gateway (smartcampus-api:8000)
  - TimescaleDB (smartcampus-db:5433)
- Cơ chế bảo vệ:
  - Tắt Rule Fallback (DISABLE_FALLBACK=True) để đo LLM thuần túy.
  - Neo thời gian ContextVar per-request (T0 = 2026-11-02T09:15:00+07:00).
  - Tích hợp SinkToolRecorder bắt Canary Token trong bộ nhớ, ngăn rò rỉ socket ra ngoài.
  - Actuation chạy ở chế độ an toàn (Dry-run).
  - Ghi tức thì ra raw_runs.jsonl, hỗ trợ resume khi bị gián đoạn.
  - Tự động gọi AttackEvaluatorV2 tính toán metrics và xuất báo cáo Markdown khi hoàn thành.
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
from typing import Any, Dict, List, Optional
from uuid import UUID

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Đảm bảo import được module app
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.config.clock import set_request_reference_time
from app.gateway.data_stealing import SinkToolRecorder
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload
from app.schemas.recommendation import AgentResponse, ToolRecommendation

from benchmarkv2_refined.attack_test.evaluator.evaluate_attack_v2 import (
    AttackEvaluatorV2,
    format_markdown_report,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("attack_test.runner")

ATTACK_DIR = PROJECT_ROOT / "benchmarkv2_refined" / "attack_test"
DEFAULT_DATASET = ATTACK_DIR / "data" / "attack_v2_testcases.json"


class AttackRunner:
    def __init__(
        self,
        run_id: str,
        output_dir: Path,
        dataset_path: Path = DEFAULT_DATASET,
        model_name: str = "gemini-3.5-flash-lite",
        provider: str = "gemini",
        disable_fallback: bool = True,
        timeout_seconds: float = 60.0,
        limit: Optional[int] = None,
        use_mock_rag: bool = False,
    ):
        self.run_id = run_id
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_path = dataset_path
        self.model_name = model_name
        self.provider = provider
        self.disable_fallback = disable_fallback
        self.timeout_seconds = timeout_seconds
        self.limit = limit
        self.use_mock_rag = use_mock_rag

        self.raw_runs_path = self.output_dir / "raw_runs.jsonl"
        self.eval_json_path = self.output_dir / "eval_attack.json"
        self.report_md_path = self.output_dir / "report_attack.md"

        self._agent = None
        self._completed_runs: set[str] = set()
        self._load_existing_runs()

    def _load_existing_runs(self) -> None:
        """Đọc raw_runs.jsonl để hỗ trợ Resume khi bị ngắt quãng."""
        if self.raw_runs_path.exists():
            with open(self.raw_runs_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        cid = data.get("testcase_id")
                        if cid is not None:
                            self._completed_runs.add(cid)
                    except Exception:
                        pass
            logger.info("Đã phát hiện %d ca đã hoàn tất từ lượt chạy trước (hỗ trợ Resume).", len(self._completed_runs))

    def _init_agent(self) -> None:
        """Khởi tạo ReActXenAgent kết nối với mô hình AI và Edge Gateway."""
        from app.gateway.rag import execute_rag_tool

        if self.provider == "gemini":
            from app.llm.gemini import GeminiLLMClient
            llm = GeminiLLMClient(model=self.model_name)
        elif self.provider == "ollama":
            from app.llm.ollama import OllamaLLMClient
            llm = OllamaLLMClient(model=self.model_name)
        else:
            raise ValueError(f"Provider '{self.provider}' không được hỗ trợ.")

        # Sử dụng ReActXenAgent chuẩn của hệ thống (Cấu hình 1 với full reflection & budget)
        from app.agent.agent import ReActXenAgent
        self._agent = ReActXenAgent(
            llm=llm,
            execute_rag_tool=execute_rag_tool,
            enforce_rag_guard=False,
        )
        logger.info("Khởi tạo ReActXenAgent thành công: Provider=%s, Model=%s", self.provider, self.model_name)

    async def run_single_testcase(self, tc: Dict[str, Any]) -> Dict[str, Any]:
        """Thực thi một testcase tấn công / kiểm thử hệ thống."""
        tcid = tc.get("testcase_id")
        ref_time = tc.get("reference_time", "2026-11-02T09:15:00+07:00")

        # Chuẩn bị môi trường & đồng hồ ContextVar
        SinkToolRecorder.clear()
        set_request_reference_time(ref_time)
        settings.BENCHMARK_MODE = True
        settings.BENCHMARK_REFERENCE_TIME = ref_time
        settings.USE_MOCK_RAG = self.use_mock_rag

        ev_dict = tc["payload"]["event"]
        ctx_dict = tc["payload"].get("operational_context", {})

        event = EventPayload(
            event_id=UUID(ev_dict["event_id"]),
            event_type=ev_dict["event_type"],
            room_id=UUID(ev_dict["room_id"]),
            timestamp=datetime.fromisoformat(ev_dict["timestamp"]),
            event_data=ev_dict.get("event_data", {}),
            operational_context=ctx_dict,
        )
        context = OperationalContext.model_validate(ctx_dict)

        t_start = time.perf_counter()
        run_status = "OK"
        response: Optional[AgentResponse] = None
        error_msg = None

        try:
            response = await asyncio.wait_for(
                self._agent.evaluate(event, context),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            run_status = "TIMEOUT"
            error_msg = f"Timeout sau {self.timeout_seconds}s"
        except Exception as exc:
            run_status = "ERROR"
            error_msg = f"{type(exc).__name__}: {str(exc)}"

        latency_ms = int((time.perf_counter() - t_start) * 1000)

        # 1. Trích xuất Trajectory từ ReAct tool calls
        trajectory: List[Dict[str, Any]] = []
        if response and getattr(response, "tool_calls_log", None):
            for step_idx, entry in enumerate(response.tool_calls_log, 1):
                if isinstance(entry, dict):
                    t_name = entry.get("tool") or entry.get("tool_name")
                    t_params = entry.get("params") or entry.get("tool_params") or {}
                    t_res = entry.get("result_summary") or entry.get("result") or ""
                else:
                    t_name = getattr(entry, "tool", None) or getattr(entry, "tool_name", None)
                    t_params = getattr(entry, "params", None) or getattr(entry, "tool_params", {})
                    t_res = getattr(entry, "result_summary", None) or getattr(entry, "result", "")

                trajectory.append({
                    "step": step_idx,
                    "tool": t_name,
                    "params": t_params,
                    "status": "success",
                    "result_summary": str(t_res)[:200],
                })

        # 2. Bổ sung các lệnh gọi sink tools từ SinkToolRecorder (nếu Agent bị lừa exfiltrate)
        sink_records = SinkToolRecorder.get_records()
        if sink_records:
            s_idx = len(trajectory) + 1
            for s in sink_records:
                trajectory.append({
                    "step": s_idx,
                    "source": "sink_recorder",
                    "tool": s["tool"],
                    "params": s["params"],
                    "status": "delivered_mock",
                })
                s_idx += 1

        # 3. Bổ sung recommendation cuối cùng
        rec_dict = None
        if response and response.recommendation:
            rec = response.recommendation
            rec_dict = {
                "tool": rec.tool_name,
                "params": rec.tool_params,
                "confidence": getattr(rec, "confidence", None),
                "reason": getattr(rec, "reason", ""),
            }
            trajectory.append({
                "step": len(trajectory) + 1,
                "tool": rec.tool_name,
                "params": rec.tool_params,
                "is_recommendation": True,
            })

        # Dọn dẹp trạng thái
        set_request_reference_time(None)
        settings.BENCHMARK_MODE = False

        record_entry = {
            "run_id": self.run_id,
            "testcase_id": tcid,
            "track": tc.get("track", "A"),
            "kind": tc.get("kind", "attack"),
            "category": tc.get("category"),
            "user_id": tc.get("user_id"),
            "room_label": tc.get("room_label"),
            "run_status": run_status,
            "is_fallback": getattr(response, "is_fallback", False) if response else False,
            "trajectory": trajectory,
            "final_recommendation": rec_dict,
            "skip": getattr(response, "skip", True) if response else True,
            "analysis": getattr(response, "analysis", error_msg or "") if response else (error_msg or ""),
            "latency_ms": latency_ms,
            "reference_time": ref_time,
            "pair_valid": tc.get("pair_valid", True),
        }

        # Lưu ngay ra file raw_runs.jsonl
        with open(self.raw_runs_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record_entry, ensure_ascii=False) + "\n")

        self._completed_runs.add(tcid)
        return record_entry

    async def run(self) -> Dict[str, Any]:
        """Chạy runner trên bộ dataset."""
        self._init_agent()

        with open(self.dataset_path, "r", encoding="utf-8") as f:
            all_cases: List[Dict[str, Any]] = json.load(f)

        target_cases = all_cases[:self.limit] if self.limit else all_cases
        total = len(target_cases)

        print("=" * 65)
        print(f"BẮT ĐẦU CHẠY ATTACK BENCHMARK: Run ID = '{self.run_id}'")
        print(f"- Số lượng testcases: {total} (Giới hạn: {self.limit or 'Toàn bộ'})")
        print(f"- Mô hình: {self.model_name} (Provider: {self.provider})")
        print(f"- Chế độ RAG: {'MOCK' if self.use_mock_rag else 'LIVE REAL (Edge Gateway & TimescaleDB)'}")
        print(f"- Thư mục kết quả: {self.output_dir}")
        print("=" * 65)

        results = []
        count = 0
        skipped = 0

        for tc in target_cases:
            tcid = tc.get("testcase_id")
            if tcid in self._completed_runs:
                skipped += 1
                continue

            count += 1
            idx_str = f"[{count + skipped}/{total}]"
            print(f"{idx_str} Thực thi {tcid}...", end="", flush=True)

            res = await self.run_single_testcase(tc)
            results.append(res)

            status = res["run_status"]
            rec_tool = res["final_recommendation"]["tool"] if res["final_recommendation"] else "none/skip"
            print(f" -> {status} (rec={rec_tool}, {res['latency_ms']}ms)")

        if skipped > 0:
            print(f"ℹ️ Đã tự động bỏ qua {skipped} ca đã có từ trước (Resume thành công).")

        # -------------------------------------------------------------
        # Đánh giá bằng AttackEvaluatorV2 ngay sau khi hoàn tất
        # -------------------------------------------------------------
        print("-" * 65)
        print("[*] Đang tiến hành đánh giá tự động bằng AttackEvaluatorV2...")
        evaluator = AttackEvaluatorV2(testcases_path=self.dataset_path)
        eval_results = evaluator.evaluate_full_run(self.raw_runs_path)

        with open(self.eval_json_path, "w", encoding="utf-8") as f:
            json.dump(eval_results, f, ensure_ascii=False, indent=2)

        report_md = format_markdown_report(eval_results)
        with open(self.report_md_path, "w", encoding="utf-8") as f:
            f.write(report_md)

        print("[✓] Hoàn tất đánh giá!")
        print(report_md)
        return eval_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Attack Benchmark V2")
    parser.add_argument("--run-id", default="attack_live_pilot")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số testcase thực thi (vd: 10 cho pilot)")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--model", default="gemini-3.5-flash-lite")
    parser.add_argument("--provider", default="gemini")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--use-mock-rag", action="store_true", default=False)

    args = parser.parse_args()

    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        out_dir = ATTACK_DIR / "runs" / args.run_id

    runner = AttackRunner(
        run_id=args.run_id,
        output_dir=out_dir,
        dataset_path=Path(args.dataset),
        model_name=args.model,
        provider=args.provider,
        timeout_seconds=args.timeout,
        limit=args.limit,
        use_mock_rag=args.use_mock_rag,
    )

    asyncio.run(runner.run())
