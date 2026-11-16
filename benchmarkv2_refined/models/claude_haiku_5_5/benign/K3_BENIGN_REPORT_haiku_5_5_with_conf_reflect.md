# BÁO CÁO BENIGN BENCHMARK K=1 (claude-haiku-5-5 | with_conf_reflect)

> **Provider:** `anthropic` | **Model:** `claude-haiku-5-5` | **Config:** `with_conf_reflect`

| Chỉ số (Metric) | r1 | r2 | r3 | **Mean** | **Std** |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Benign Utility / Accuracy (BU)** | — | — | — | **85.00%** | ± 0.00% |
| **BU (Nhóm cần hành động bảo vệ)** | — | — | — | **62.50%** | ± 0.00% |
| **BU (Nhóm an toàn / skip đúng)** | — | — | — | **100.00%** | ± 0.00% |
| **Action Compliance (V2)** | — | — | — | **77.00%** | ± 0.00% |
| **Classification Accuracy (V2)** | — | — | — | **51.00%** | ± 0.00% |
| **Outcome & Safety (V2)** | — | — | — | **77.00%** | ± 0.00% |
| **Safety Violations (Crit/Maj/Min tổng 3 lượt)** | — | — | — | 3 / 0 / 1 | — |

- Dùng file `D:\SmartCampus\AI + Backend\benchmarkv2_refined\benign_test\results\k3_benign_summary_haiku_5_5_with_conf_reflect.json` cho tham số `--benign-summary` khi chạy `run_advanced_attack_k3_pipeline.py` để tính chính xác `Delta U = BU - UA`.