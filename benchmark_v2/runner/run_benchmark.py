#!/usr/bin/env python3
"""
benchmark_v2/runner/run_benchmark.py
------------------------------------
Runner thực thi Benchmark v2 chuẩn hóa (§9 Master Plan):
- Hỗ trợ cả 2 Track: Track A (315 ca) và Track B (16 ca).
- Hỗ trợ LLM thực tế (Gemini, Ollama) hoặc Synthetic Agent (cho Sanity Check Phase D3).
- Ghi vết Trajectory chuẩn xác theo Phụ lục E (Phụ lục D/E Master Plan).
- Tắt Fallback (DISABLE_FALLBACK=True) cho các headline run.
- Neo thời gian ContextVar theo từng testcase.
- Hỗ trợ resume (tiếp tục chạy khi bị ngắt quãng bằng cách đọc raw_runs.jsonl).
- Tích hợp ghi nhận lệnh gọi sink tool (Data Stealing SinkToolRecorder).
"""

from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
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
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.config.clock import set_request_reference_time
from app.gateway.data_stealing import SinkToolRecorder
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload
from app.schemas.recommendation import AgentResponse, ToolRecommendation

logger = logging.getLogger("benchmark_v2.runner")


class BenchmarkRunner:
    def __init__(
        self,
        run_id: str,
        output_dir: Path,
        model_name: str = "gemini-3.5-flash-lite",
        provider: str = "gemini",
        synthetic_agent: Optional[str] = None,
        disable_fallback: bool = True,
        timeout_seconds: float = 60.0,
        k_repeats: int = 1,
    ):
        self.run_id = run_id
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self.provider = provider
        self.synthetic_agent = synthetic_agent
        self.disable_fallback = disable_fallback
        self.timeout_seconds = timeout_seconds
        self.k_repeats = k_repeats
        self.raw_runs_path = self.output_dir / "raw_runs.jsonl"
        self.manifest_path = self.output_dir / "manifest.json"

        self._agent = None
        self._completed_runs: set[tuple[str, int]] = set()
        self._canary_by_user: Dict[str, List[str]] = defaultdict(list)
        self._load_canaries()
        self._load_existing_runs()

    def _load_canaries(self) -> None:
        """Đọc danh sách canary tokens theo từng phòng/user_id."""
        env_spec_file = PROJECT_ROOT / "benchmark_v2" / "data" / "env_spec.json"
        if env_spec_file.exists():
            with open(env_spec_file, "r", encoding="utf-8") as f:
                spec = json.load(f)
                for r in spec.get("rooms", []):
                    uid = r.get("user_id")
                    rid = r.get("room_id")
                    for n in r.get("notes_with_canary", []):
                        tokens = re.findall(r"CNRY-[A-Z0-9\-]+", n.get("text", ""))
                        self._canary_by_user[uid].extend(tokens)
                        self._canary_by_user[rid].extend(tokens)

    def _load_existing_runs(self) -> None:
        """Đọc raw_runs.jsonl để hỗ trợ tính năng resume."""
        if self.raw_runs_path.exists():
            with open(self.raw_runs_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        cid = data.get("testcase_id")
                        ridx = data.get("repeat_idx", 0)
                        if cid is not None:
                            self._completed_runs.add((cid, ridx))
                    except Exception:
                        pass
            logger.info("Đã phát hiện %d ca đã hoàn thành từ lượt chạy trước (hỗ trợ Resume).", len(self._completed_runs))

    def _init_agent(self) -> None:
        """Khởi tạo agent thực tế nếu không dùng synthetic agent."""
        if self.synthetic_agent:
            logger.info("Runner sử dụng Synthetic Agent: '%s' (không tốn LLM API)", self.synthetic_agent)
            return

        from app.agent.agent import ReActXenAgent
        from app.gateway.rag import execute_rag_tool

        if self.provider == "gemini":
            from app.llm.gemini import GeminiLLMClient
            llm = GeminiLLMClient(model=self.model_name)
        elif self.provider == "ollama":
            from app.llm.ollama import OllamaLLMClient
            llm = OllamaLLMClient(model=self.model_name)
        else:
            raise ValueError(f"Provider '{self.provider}' không được hỗ trợ.")

        self._agent = ReActXenAgent(
            llm=llm,
            execute_rag_tool=execute_rag_tool,
            enforce_rag_guard=False,
        )

    async def _execute_synthetic(self, tc: Dict[str, Any]) -> AgentResponse:
        """Hành vi của 4 Synthetic Agents phục vụ Sanity Test (D3)."""
        mode = self.synthetic_agent.lower()
        ev_id = UUID(tc["payload"]["event"]["event_id"])
        room_label = tc.get("room_label", "A104")
        room_id = tc.get("room_id")

        if mode == "broken":
            # Broken: Trả lỗi / unparsed
            raise RuntimeError("Synthetic Broken Agent: JSON Parse Error / Provider failure simulation")

        elif mode == "obedient":
            # Obedient: Luôn làm đúng điều payload yêu cầu
            kind = tc.get("kind", "attack")
            cat = tc.get("category")
            goal = tc.get("goal") or {}
            gtype = goal.get("type")

            tool_calls = []
            rec = None

            if kind == "benign":
                # Đối với benign, làm theo expected_benign
                exp = tc.get("expected_benign", {})
                req = exp.get("required_any_of", [])
                if req and req[0].get("tool") != "none":
                    act = req[0]
                    rec = ToolRecommendation(
                        tool_name=act.get("tool"),
                        tool_params=act.get("params", {}),
                        reason="Obedient following benign instructions",
                        confidence=1.0,
                    )
            elif cat in ["DH-A", "DH-S"]:
                tname = goal.get("tool")
                tparams = goal.get("params", {})
                rec = ToolRecommendation(
                    tool_name=tname,
                    tool_params=tparams,
                    reason=f"Obedient executing attacker {cat} goal",
                    confidence=1.0,
                )
            elif cat == "SUP":
                # SUP: bỏ qua không làm hành động bảo vệ
                rec = None
            elif cat == "DS":
                # DS: Gọi S1 đọc canary, rồi gọi S2 gửi canary ra ngoài
                s1_tool = goal.get("s1", {}).get("tool", "read_room_notes")
                s2_tool = goal.get("s2", {}).get("tools_any_of", ["http_post"])[0]

                # Lấy canary từ env_spec cho room này
                uid = tc.get("user_id")
                room_canaries = self._canary_by_user.get(uid, []) or self._canary_by_user.get(room_id, [])
                canary_sample = room_canaries[0] if room_canaries else "CNRY-PIN-TEST"

                # Giả lập lệnh đọc S1
                tool_calls.append({"tool": s1_tool, "params": {"room_id": room_id}, "result": f"Notes: {canary_sample}"})
                # Gọi S2 qua SinkToolRecorder
                SinkToolRecorder.record(s2_tool, {"data": f"Exfiltrated payload: {canary_sample}"})

            return AgentResponse(
                event_id=ev_id,
                recommendation=rec,
                analysis="Synthetic Obedient Agent finished.",
                skip=(rec is None),
                tool_calls_log=tool_calls,
                is_fallback=False,
            )

        elif mode == "deaf":
            # Deaf: Luôn làm đúng nhiệm vụ benign, hoàn toàn phớt lờ injection
            exp = tc.get("expected_benign", {})
            req = exp.get("required_any_of", [])
            rec = None
            if req and req[0].get("tool") not in ["none", "finish"]:
                act = req[0]
                rec = ToolRecommendation(
                    tool_name=act.get("tool"),
                    tool_params=act.get("params", {}),
                    reason="Deaf agent executing legitimate benign duty",
                    confidence=1.0,
                )
            return AgentResponse(
                event_id=ev_id,
                recommendation=rec,
                analysis="Synthetic Deaf Agent completed benign requirement.",
                skip=(rec is None),
                is_fallback=False,
            )

        elif mode == "paranoid":
            # Paranoid: Luôn trả none/skip, không bao giờ gọi bất kỳ action tool nào
            return AgentResponse(
                event_id=ev_id,
                recommendation=None,
                analysis="Synthetic Paranoid Agent: reject all action tools.",
                skip=True,
                is_fallback=False,
            )
        else:
            raise ValueError(f"Chế độ synthetic agent không hợp lệ: {mode}")

    async def run_single_testcase(self, tc: Dict[str, Any], repeat_idx: int = 0) -> Dict[str, Any]:
        """Thực thi một testcase đơn lẻ và trả về bản ghi log chuẩn Phụ lục E."""
        tcid = tc["testcase_id"]
        ref_time = tc.get("reference_time", "2026-11-02T09:15:00+07:00")

        # Chuẩn bị môi trường & đồng hồ ContextVar
        SinkToolRecorder.clear()
        set_request_reference_time(ref_time)
        settings.BENCHMARK_MODE = True
        settings.BENCHMARK_REFERENCE_TIME = ref_time

        ev_dict = tc["payload"]["event"]
        ctx_dict = tc["payload"].get("operational_context", {})

        # Parse Event & Context
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
        fallback_reason = None
        response = None
        error_msg = None

        tok_in_before = getattr(self._agent._llm, "total_input_tokens", 0) if (hasattr(self, "_agent") and hasattr(self._agent, "_llm")) else 0
        tok_out_before = getattr(self._agent._llm, "total_output_tokens", 0) if (hasattr(self, "_agent") and hasattr(self._agent, "_llm")) else 0

        try:
            if self.synthetic_agent:
                response = await self._execute_synthetic(tc)
            else:
                if self.disable_fallback:
                    # Chạy evaluate trực tiếp có bảo vệ timeout
                    response = await asyncio.wait_for(
                        self._agent.evaluate(event, context),
                        timeout=self.timeout_seconds,
                    )
                else:
                    response = await self._agent.evaluate(event, context)

            if response.is_fallback:
                fallback_reason = response.skip_reason or "Fallback triggered"

        except asyncio.TimeoutError:
            run_status = "TIMEOUT"
            error_msg = f"Timeout sau {self.timeout_seconds}s"
        except Exception as exc:
            run_status = "ERROR"
            error_msg = f"{type(exc).__name__}: {str(exc)}"

        latency_ms = int((time.perf_counter() - t_start) * 1000)

        # Trích xuất toàn bộ Trajectory
        trajectory: List[Dict[str, Any]] = []
        step_idx = 1

        if response is not None:
            # 1. Các tool gọi trong ReAct loop
            for call in response.tool_calls_log:
                c_dict = call if isinstance(call, dict) else call.model_dump()
                trajectory.append({
                    "source": "react_action",
                    "step": step_idx,
                    "tool": c_dict.get("tool"),
                    "params": c_dict.get("params", {}),
                })
                step_idx += 1

            # 2. Các sink tool ghi nhận trong SinkToolRecorder
            for sink in SinkToolRecorder.get_records():
                if not any(t["tool"] == sink["tool"] and t["params"] == sink["params"] for t in trajectory):
                    trajectory.append({
                        "source": "sink_action",
                        "step": step_idx,
                        "tool": sink["tool"],
                        "params": sink["params"],
                    })
                    step_idx += 1

            # 3. Hành động đề xuất trong finish
            if response.recommendation is not None:
                rec_dict = response.recommendation.model_dump()
                trajectory.append({
                    "source": "recommendation",
                    "step": step_idx,
                    "tool": rec_dict.get("tool_name"),
                    "params": rec_dict.get("tool_params", {}),
                })

        # Dọn dẹp trạng thái
        set_request_reference_time(None)
        settings.BENCHMARK_MODE = False

        tok_in_after = getattr(self._agent._llm, "total_input_tokens", 0) if (hasattr(self, "_agent") and hasattr(self._agent, "_llm")) else 0
        tok_out_after = getattr(self._agent._llm, "total_output_tokens", 0) if (hasattr(self, "_agent") and hasattr(self._agent, "_llm")) else 0
        tokens_used = {
            "in": max(0, tok_in_after - tok_in_before),
            "out": max(0, tok_out_after - tok_out_before),
        }

        record_entry = {
            "run_id": self.run_id,
            "testcase_id": tcid,
            "track": tc.get("track", "A"),
            "kind": tc.get("kind", "attack"),
            "category": tc.get("category"),
            "user_id": tc.get("user_id"),
            "room_label": tc.get("room_label"),
            "repeat_idx": repeat_idx,
            "run_status": run_status,
            "is_fallback": getattr(response, "is_fallback", False) if response else False,
            "fallback_reason": fallback_reason or error_msg,
            "retry_count": 0,
            "trajectory": trajectory,
            "final_recommendation": (
                response.recommendation.model_dump() if (response and response.recommendation) else None
            ),
            "skip": getattr(response, "skip", True) if response else True,
            "analysis": getattr(response, "analysis", error_msg or "") if response else (error_msg or ""),
            "latency_ms": latency_ms,
            "tokens": tokens_used,
            "env_version": "2.0",
            "reference_time": ref_time,
            "pair_valid": tc.get("pair_valid", True),
        }

        # Ghi ngay lập tức ra raw_runs.jsonl (bảo đảm an toàn dữ liệu, resume được)
        with open(self.raw_runs_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record_entry, ensure_ascii=False) + "\n")

        self._completed_runs.add((tcid, repeat_idx))
        return record_entry

    async def run_benchmark(
        self,
        testcases: List[Dict[str, Any]],
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Chạy toàn bộ danh sách testcase qua k lần lặp."""
        self._init_agent()
        filtered = testcases[:limit] if limit else testcases
        total_runs = len(filtered) * self.k_repeats

        print("=" * 65)
        print(f"BẮT ĐẦU CHẠY BENCHMARK v2: Run ID = '{self.run_id}'")
        print(f"- Số testcase: {len(filtered)} | Số lần lặp k = {self.k_repeats} | Tổng lượt: {total_runs}")
        print(f"- Mô hình: {self.model_name} (Provider: {self.provider})")
        if self.synthetic_agent:
            print(f"- Chế độ: SYNTHETIC AGENT '{self.synthetic_agent}'")
        print(f"- File kết quả: {self.raw_runs_path}")
        print("=" * 65)

        results = []
        count = 0
        skipped_count = 0

        for r_idx in range(self.k_repeats):
            for tc in filtered:
                tcid = tc["testcase_id"]
                if (tcid, r_idx) in self._completed_runs:
                    skipped_count += 1
                    continue

                count += 1
                prefix = f"[{count + skipped_count}/{total_runs}]"
                print(f"{prefix} Chạy {tcid} (Lần #{r_idx + 1})...", end="", flush=True)

                res = await self.run_single_testcase(tc, repeat_idx=r_idx)
                results.append(res)

                status = res["run_status"]
                rec_tool = res["final_recommendation"]["tool_name"] if res["final_recommendation"] else "none/skip"
                print(f" -> {status} (tool={rec_tool}, {res['latency_ms']}ms)")

        if skipped_count > 0:
            print(f"ℹ️ Đã tự động bỏ qua {skipped_count} lượt đã có sẵn từ trước (Resume thành công).")

        # Cập nhật manifest.json
        manifest = {
            "run_id": self.run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "model_name": self.model_name,
            "provider": self.provider,
            "synthetic_agent": self.synthetic_agent,
            "k_repeats": self.k_repeats,
            "total_executed": len(self._completed_runs),
            "raw_runs_file": self.raw_runs_path.name,
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        print("=" * 65)
        print(f"HOÀN THÀNH LƯỢT CHẠY BENCHMARK: {len(self._completed_runs)} bản ghi tại {self.raw_runs_path}")
        print("=" * 65)
        return results


def load_dataset(data_dir: Path, track: str = "all", user_filter: Optional[str] = None, pilot: bool = False) -> List[Dict[str, Any]]:
    """Tải testcases theo cấu hình track, user và pilot."""
    cases = []
    track_a_path = data_dir / "generated" / "trackA_testcases.json"
    track_b_path = data_dir / "trackB_testcases.json"

    if track in ["A", "all"] and track_a_path.exists():
        with open(track_a_path, "r", encoding="utf-8") as f:
            cases.extend(json.load(f))

    if not pilot and track in ["B", "all"] and track_b_path.exists():
        with open(track_b_path, "r", encoding="utf-8") as f:
            cases.extend(json.load(f))

    if pilot:
        pilot_atk = {
            "A-DH-A-001", "A-DH-A-002", "A-DH-A-003",
            "A-DH-S-001", "A-DH-S-002",
            "A-SUP-001", "A-SUP-002",
            "A-DS-001", "A-DS-002", "A-DS-003",
        }
        cases = [c for c in cases if c.get("kind") == "benign" or any(a in c.get("testcase_id", "") for a in pilot_atk)]

    if user_filter:
        cases = [c for c in cases if c.get("user_id") == user_filter]

    return cases


def main():
    parser = argparse.ArgumentParser(description="Runner thực thi Benchmark v2")
    parser.add_argument("--track", type=str, default="all", choices=["A", "B", "all"], help="Track cần chạy (A, B hoặc all)")
    parser.add_argument("--user", type=str, default=None, help="Lọc theo User Case (U1..U5)")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số lượng testcase cần chạy")
    parser.add_argument("--k", type=int, default=1, help="Số lần lặp lại k (mặc định 1)")
    parser.add_argument("--model", type=str, default="gemini-3.5-flash-lite", help="Tên model LLM")
    parser.add_argument("--provider", type=str, default="gemini", choices=["gemini", "ollama"], help="LLM Provider")
    parser.add_argument("--synthetic-agent", type=str, default=None, choices=["obedient", "deaf", "paranoid", "broken"], help="Dùng agent giả cho Sanity Check (D3)")
    parser.add_argument("--timeout", type=float, default=60.0, help="Timeout cho mỗi testcase (giây)")
    parser.add_argument("--run-id", type=str, default=None, help="ID định danh lượt chạy")
    parser.add_argument("--pilot", action="store_true", help="Chạy tập Pilot theo chuẩn §10.1 (5 users x 10 attackers + 15 BU = 65 ca)")
    args = parser.parse_args()

    base_dir = PROJECT_ROOT / "benchmark_v2"
    data_dir = base_dir / "data"

    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    pilot_tag = "pilot_" if args.pilot else ""
    agent_tag = f"synth_{args.synthetic_agent}" if args.synthetic_agent else args.model.replace(":", "_").replace("/", "_")
    run_id = args.run_id or f"{pilot_tag}{now_str}_{agent_tag}_k{args.k}"
    out_dir = base_dir / "results" / run_id

    testcases = load_dataset(data_dir, track=args.track, user_filter=args.user, pilot=args.pilot)
    if not testcases:
        print("Lỗi: Không tìm thấy testcase nào phù hợp với bộ lọc!")
        sys.exit(1)

    runner = BenchmarkRunner(
        run_id=run_id,
        output_dir=out_dir,
        model_name=args.model,
        provider=args.provider,
        synthetic_agent=args.synthetic_agent,
        timeout_seconds=args.timeout,
        k_repeats=args.k,
    )

    asyncio.run(runner.run_benchmark(testcases, limit=args.limit))


if __name__ == "__main__":
    main()
