# benchmarkv2_refined: SmartCampus Agent Safety Benchmark

Thư mục chia làm 3 phần:
- **`framework/`**: code và dữ liệu dùng chung. Không chứa kết quả.
- **`models/<model>/`**: toàn bộ kết quả của một model (benign, attack, clean-twin, log).
- **`reports/`**: báo cáo tổng hợp, so sánh giữa các model.

Ground truth duy nhất: [`framework/ground_truth/GROUND_TRUTH_ATTACK.md`](framework/ground_truth/GROUND_TRUTH_ATTACK.md) (v2.1.0). Số liệu chuẩn là số chấm theo spec này.

```
benchmarkv2_refined/
├── framework/
│   ├── ground_truth/        GROUND_TRUTH_ATTACK.md (chuẩn), GROUND_TRUTH_BENIGN.md,
│   │                        ground_truth_v2.json (tập hành động ưu tiên, đồng nghĩa, chất lượng alert),
│   │                        evaluate_advanced_attack_v2.py, evaluate_benign_strict.py   ← evaluator chuẩn
│   ├── benign/              data/ (benign_v2_testcases.json), runner/, evaluator/, agents/, tests/,
│   │                        run_benign_k3_pipeline.py
│   ├── attack_advanced/     data/ (advanced_attack_testcases.json, clean_twin_sup_testcases.json, attackers),
│   │                        runner/, evaluator/ (luật cũ, dùng kiểm tra hồi quy), analysis/, tests/,
│   │                        run_advanced_attack_k3_pipeline.py, run_clean_twin_k3_pipeline.py, synthesize_attack_k3.py
│   ├── attack_basic/        Phase 2 (60 ca), giữ để tham khảo
│   └── env/db_migration_bundle/
├── models/                  tên thư mục = tên model đã chuẩn hoá (dấu '-', '.', ':' → '_')
│   ├── gemini_3_5_flash_lite/   benign/, attack_advanced/ (r1–r3, pilot), clean_twin_sup/ (r1–r3),
│   │                            attack_basic/, analysis/, audit/ (audit phương pháp luận)
│   ├── gpt_5_6_luna/            attack_advanced/, logs/
│   ├── gpt_6_luna/              benign/, attack_advanced/ (r1, r2, pilot), logs/
│   ├── deepseek_flash/          benign/, attack_advanced/ (r1, r2_incomplete, pilot), logs/
│   ├── claude_haiku_5_5/        benign/, attack_advanced/, logs/
│   └── glm_5_3_flash/           benign/, attack_advanced/, logs/
└── reports/
    ├── MODEL_COMPARISON_BU_ASR.md   so sánh BU, ASR, taxonomy giữa các model
    ├── RESULTS_STRICT.md            kết quả theo ground truth chuẩn (cột STRICT)
    ├── CLEAN_TWIN_PLAN.md           kế hoạch clean-twin SUP (checklist)
    ├── scored/                      output của evaluator chuẩn (attack_advanced/, benign/, clean_twin_sup_gemini/)
    └── summary_report/              báo cáo tổng kết (.md/.docx), hướng dẫn chạy local
```

## Chạy thực nghiệm (từ thư mục `AI + Backend/`)

Kết quả tự ghi vào `benchmarkv2_refined/models/<model>/<suite>/<run_id>`.

```bash
# Benign k=3
python benchmarkv2_refined/framework/benign/run_benign_k3_pipeline.py --provider anthropic --model claude-haiku-5-5

# Advanced attack k=3
python benchmarkv2_refined/framework/attack_advanced/run_advanced_attack_k3_pipeline.py --provider anthropic --model claude-haiku-5-5 --tag haiku_5_5 --benign-baseline 0.85

# Clean-twin SUP k=3 (có thể dùng --dataset để chạy file con)
python benchmarkv2_refined/framework/attack_advanced/run_clean_twin_k3_pipeline.py --provider zhipu --model glm-5.3-flash --tag glm_5_3_flash
```

**Cơ chế bảo vệ dữ liệu:**
- Runner ghi nối tiếp (append) và resume `raw_runs.jsonl`, không xoá dữ liệu cũ.
- `synthesize_attack_k3.py` không ghi đè báo cáo tổng hợp đã có; nếu trùng tên, file mới được thêm hậu tố thời gian.
- Pipeline clean-twin dừng lại nếu thư mục run đã tồn tại.

**Lưu ý:** file `framework/attack_advanced/STOP_AFTER_R2.flag` đang tồn tại, nên mọi run có `r3` trong tên sẽ bị dừng. Xoá file này nếu muốn chạy đủ k=3.

## Chấm điểm theo ground truth chuẩn (từ thư mục `benchmarkv2_refined/`)

Chấm hoàn toàn từ `raw_runs.jsonl`, không cần chạy lại agent.

```bash
python framework/ground_truth/evaluate_advanced_attack_v2.py --check-l0 \
  --runs models/claude_haiku_5_5/attack_advanced/haiku_5_5_adv_r1/raw_runs.jsonl --benign-baseline 0.85
python framework/ground_truth/evaluate_benign_strict.py \
  --runs models/claude_haiku_5_5/benign/haiku_5_5_with_conf_reflect_r1/raw_runs.jsonl --label haiku
```

Mặc định output ghi vào `reports/scored/attack_advanced/` và `reports/scored/benign/`. Cột `STRICT` là số chuẩn; cột `L0` là luật cũ, chỉ dùng để kiểm tra hồi quy.

## Lưu ý về môi trường
- **Trạng thái RAG phải giống nhau giữa các model được so sánh.** Kiểm tra bằng pilot: `get_room_history.contextual_summary` phải cùng dạng. Gemini benign và attack r1 chạy ở trạng thái "seed" (E1); mọi run khác chạy ở trạng thái "sau rollup" (E2). Xem `GROUND_TRUTH_ATTACK.md` §10.
- **Một số file JSON cũ (`round_dirs`, …) còn ghi đường dẫn tuyệt đối tới vị trí trước khi tái cấu trúc (16/11/2026).** Đây chỉ là metadata, không ảnh hưởng việc chấm điểm.
