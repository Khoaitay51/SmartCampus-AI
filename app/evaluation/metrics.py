"""
app/evaluation/metrics.py
--------------------------
Tính toán các chỉ số đánh giá hiệu năng agent (Accuracy, Latency, Precision, Confidence).
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvaluationMetrics:
    total_scenarios: int = 0
    passed_scenarios: int = 0
    accuracy: float = 0.0
    avg_latency_seconds: float = 0.0
    avg_confidence: float = 0.0

    def compute(self, results: list[dict[str, Any]]) -> None:
        if not results:
            return
        self.total_scenarios = len(results)
        self.passed_scenarios = sum(1 for r in results if r.get("passed", False))
        self.accuracy = self.passed_scenarios / self.total_scenarios
        self.avg_latency_seconds = sum(r.get("latency", 0.0) for r in results) / self.total_scenarios
        self.avg_confidence = sum(r.get("confidence", 0.0) for r in results) / self.total_scenarios
