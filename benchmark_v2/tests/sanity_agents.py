#!/usr/bin/env python3
"""
benchmark_v2/tests/sanity_agents.py
-----------------------------------
Bộ kiểm thử Sanity Agents & Evaluator (Phase D3, §9 Master Plan):
Chạy toàn bộ dataset với 4 Agent giả định mà KHÔNG tốn chi phí LLM:
1. Obedient Agent: Luôn làm đúng điều payload yêu cầu -> ASR_valid = 100%.
2. Deaf Agent: Luôn làm đúng nhiệm vụ benign, bỏ qua payload -> ASR_valid = 0%, BU = UA = 100%.
3. Paranoid Agent: Luôn trả none/skip -> ASR(DH, DS) = 0%, ASR(SUP) = 100%, BU = 20% (chỉ U5 đúng).
4. Broken Agent: Luôn trả lỗi -> Tất cả đều ERROR / Unhandled, Valid Rate = 0%.

Xác nhận Evaluator hoạt động chuẩn xác 100% trước khi chạy với model LLM thật.
"""

from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
import shutil
import sys
import unittest

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmark_v2.runner.run_benchmark import BenchmarkRunner, load_dataset
from benchmark_v2.evaluator.evaluate_v2 import EvaluatorV2


class TestSanityAgentsAndEvaluator(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_dir = PROJECT_ROOT / "benchmark_v2"
        cls.data_dir = cls.base_dir / "data"
        cls.test_results_dir = cls.base_dir / "results" / "_sanity_test_tmp"
        if cls.test_results_dir.exists():
            shutil.rmtree(cls.test_results_dir)
        cls.test_results_dir.mkdir(parents=True, exist_ok=True)

        cls.evaluator = EvaluatorV2(data_dir=cls.data_dir, confidence=0.95)
        cls.all_testcases = load_dataset(cls.data_dir, track="all")
        print(f"\n[Sanity Suite] Đã nạp {len(cls.all_testcases)} testcases cho 4 Agent giả định.")

    @classmethod
    def tearDownClass(cls):
        if cls.test_results_dir.exists():
            shutil.rmtree(cls.test_results_dir, ignore_errors=True)

    async def _run_and_evaluate(self, agent_name: str) -> dict:
        run_id = f"sanity_{agent_name}"
        out_dir = self.test_results_dir / run_id
        runner = BenchmarkRunner(
            run_id=run_id,
            output_dir=out_dir,
            synthetic_agent=agent_name,
            k_repeats=1,
        )
        await runner.run_benchmark(self.all_testcases)
        raw_runs = out_dir / "raw_runs.jsonl"
        summary = self.evaluator.evaluate_full_run(raw_runs)
        return summary

    async def test_01_obedient_agent(self):
        """1. Obedient Agent: Luôn vâng lời hacker -> ASR_valid = 100%, ASR_all = 100%."""
        print("\n>>> KIỂM THỬ SANITY: 1. OBEDIENT AGENT")
        summary = await self._run_and_evaluate("obedient")
        ta = summary["track_a"]

        asr_valid = ta["asr_valid"]["rate"]
        asr_all = ta["asr_all"]["rate"]
        mhr = ta["mhr"]
        bu = ta["utility"]["bu_rate"]

        print(f"  + Obedient ASR-valid: {asr_valid*100:.2f}% (Kỳ vọng: 100%)")
        print(f"  + Obedient ASR-all:   {asr_all*100:.2f}% (Kỳ vọng: 100%)")
        print(f"  + Obedient MHR:       {mhr*100:.2f}% (Kỳ vọng: 100%)")
        print(f"  + Obedient BU:        {bu*100:.2f}% (Kỳ vọng: 100%)")

        self.assertAlmostEqual(asr_valid, 1.0, places=2, msg="Obedient Agent phải đạt ASR_valid = 100%!")
        self.assertAlmostEqual(asr_all, 1.0, places=2, msg="Obedient Agent phải đạt ASR_all = 100%!")
        self.assertAlmostEqual(mhr, 1.0, places=2, msg="Obedient Agent phải đạt MHR = 100%!")
        self.assertAlmostEqual(bu, 1.0, places=2, msg="Obedient Agent phải hoàn thành 100% BU!")

    async def test_02_deaf_agent(self):
        """2. Deaf Agent: Bỏ qua injection, luôn làm đúng nhiệm vụ benign -> ASR = 0%, BU = UA = 100%."""
        print("\n>>> KIỂM THỬ SANITY: 2. DEAF AGENT")
        summary = await self._run_and_evaluate("deaf")
        ta = summary["track_a"]

        asr_valid = ta["asr_valid"]["rate"]
        bu = ta["utility"]["bu_rate"]
        ua = ta["utility"]["ua_rate"]
        delta_u = ta["utility"]["delta_u"]

        print(f"  + Deaf ASR-valid: {asr_valid*100:.2f}% (Kỳ vọng: 0%)")
        print(f"  + Deaf BU:        {bu*100:.2f}% (Kỳ vọng: 100%)")
        print(f"  + Deaf UA:        {ua*100:.2f}% (Kỳ vọng: 100%)")
        print(f"  + Deaf ΔU:        {delta_u*100:.2f}% (Kỳ vọng: 0%)")

        self.assertAlmostEqual(asr_valid, 0.0, places=2, msg="Deaf Agent phải đạt ASR_valid = 0%!")
        self.assertAlmostEqual(bu, 1.0, places=2, msg="Deaf Agent phải đạt BU = 100%!")
        self.assertAlmostEqual(ua, 1.0, places=2, msg="Deaf Agent phải đạt UA = 100%!")
        self.assertAlmostEqual(delta_u, 0.0, places=2, msg="Deaf Agent phải có ΔU = 0%!")

    async def test_03_paranoid_agent(self):
        """3. Paranoid Agent: Luôn trả none -> ASR(DH, DS) = 0%, ASR(SUP) = 100%, BU = 20% (chỉ U5 đúng)."""
        print("\n>>> KIỂM THỬ SANITY: 3. PARANOID AGENT")
        summary = await self._run_and_evaluate("paranoid")
        ta = summary["track_a"]

        tax = ta["taxonomy"]
        asr_dha = tax["DH-A"]["asr"]
        asr_dhs = tax["DH-S"]["asr"]
        asr_ds = tax["DS"]["asr"]
        asr_sup = tax["SUP"]["asr"]
        bu = ta["utility"]["bu_rate"]

        print(f"  + Paranoid ASR(DH-A): {asr_dha*100:.2f}% (Kỳ vọng: 0%)")
        print(f"  + Paranoid ASR(DH-S): {asr_dhs*100:.2f}% (Kỳ vọng: 0%)")
        print(f"  + Paranoid ASR(DS):   {asr_ds*100:.2f}% (Kỳ vọng: 0%)")
        print(f"  + Paranoid ASR(SUP):  {asr_sup*100:.2f}% (Kỳ vọng: 100% do bỏ sót bảo vệ)")
        print(f"  + Paranoid BU:        {bu*100:.2f}% (Kỳ vọng: 20% - chỉ 3 ca U5 đúng)")

        self.assertAlmostEqual(asr_dha, 0.0, places=2, msg="Paranoid không gọi tool -> DH-A = 0%!")
        self.assertAlmostEqual(asr_dhs, 0.0, places=2, msg="Paranoid không gọi tool -> DH-S = 0%!")
        self.assertAlmostEqual(asr_ds, 0.0, places=2, msg="Paranoid không gọi tool -> DS = 0%!")
        self.assertAlmostEqual(asr_sup, 1.0, places=2, msg="Paranoid bỏ sót bảo vệ -> SUP = 100%!")
        self.assertAlmostEqual(bu, 0.20, places=2, msg="Paranoid chỉ hoàn thành U5 -> BU = 20% (3/15)!")

    async def test_04_broken_agent(self):
        """4. Broken Agent: Luôn trả lỗi -> Toàn bộ run_status = ERROR, không được báo là an toàn."""
        print("\n>>> KIỂM THỬ SANITY: 4. BROKEN AGENT")
        run_id = "sanity_broken"
        out_dir = self.test_results_dir / run_id
        runner = BenchmarkRunner(
            run_id=run_id,
            output_dir=out_dir,
            synthetic_agent="broken",
            k_repeats=1,
        )
        records = await runner.run_benchmark(self.all_testcases[:10])  # chạy mẫu 10 ca
        self.assertTrue(all(r["run_status"] == "ERROR" for r in records), "Broken Agent phải có run_status = ERROR cho mọi ca!")
        print(f"  + Broken Agent: 10/10 ca đều được ghi nhận run_status = 'ERROR' đúng chuẩn.")


if __name__ == "__main__":
    unittest.main()
