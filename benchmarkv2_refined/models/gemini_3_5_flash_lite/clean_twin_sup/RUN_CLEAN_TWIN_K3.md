# Chạy clean twin k=3 (cần Gateway :8000 + TimescaleDB :5433 + GEMINI_API_KEY)

Lượt 1 đã có (nằm trong advanced_benchmark_full). Chạy thêm 2 lượt, cùng tham số, từ thư mục `AI + Backend`:

    python -m benchmarkv2_refined.advanced_attack_test.runner.run_advanced_attack --run-id clean_twin_r2 --dataset benchmarkv2_refined/advanced_attack_test/data/clean_twin_testcases.json
    python -m benchmarkv2_refined.advanced_attack_test.runner.run_advanced_attack --run-id clean_twin_r3 --dataset benchmarkv2_refined/advanced_attack_test/data/clean_twin_testcases.json

Rồi tổng hợp:

    python benchmarkv2_refined/advanced_attack_test/analysis/clean_twin.py --clean-runs benchmarkv2_refined/advanced_attack_test/runs/advanced_benchmark_full/raw_runs.jsonl benchmarkv2_refined/advanced_attack_test/runs/clean_twin_r2/raw_runs.jsonl benchmarkv2_refined/advanced_attack_test/runs/clean_twin_r3/raw_runs.jsonl
