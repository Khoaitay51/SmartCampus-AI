# BÁO CÁO BENIGN BENCHMARK K=1 (deepseek-flash | with_conf_reflect)

> **Provider:** `deepseek` | **Model:** `deepseek-flash` | **Config:** `with_conf_reflect`

| Chỉ số (Metric) | r1 | r2 | r3 | **Mean** | **Std** |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Benign Utility / Accuracy (BU)** | — | — | — | **92.00%** | ± 0.00% |
| **BU (Nhóm cần hành động bảo vệ)** | — | — | — | **80.00%** | ± 0.00% |
| **BU (Nhóm an toàn / skip đúng)** | — | — | — | **100.00%** | ± 0.00% |
| **Action Compliance (V2)** | — | — | — | **79.00%** | ± 0.00% |
| **Classification Accuracy (V2)** | — | — | — | **53.00%** | ± 0.00% |
| **Outcome & Safety (V2)** | — | — | — | **79.00%** | ± 0.00% |
| **Safety Violations (Crit/Maj/Min tổng 3 lượt)** | — | — | — | 0 / 0 / 0 | — |

- Dùng file `D:\SmartCampus\AI + Backend\benchmarkv2_refined\benign_test\results\k3_benign_summary_deepseek_flash_with_conf_reflect.json` cho tham số `--benign-summary` khi chạy `run_advanced_attack_k3_pipeline.py` để tính chính xác `Delta U = BU - UA`.