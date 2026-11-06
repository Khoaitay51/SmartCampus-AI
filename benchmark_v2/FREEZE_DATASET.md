# BIÊN BẢN ĐÓNG BĂNG DATASET BENCHMARK v2 (DATASET FREEZE MANIFEST)
**SmartCampus AI Safety Benchmark v2**  
*Mã mốc:* **GATE G3 (APPROVED)**  
*Thời điểm đóng băng:* `2026-10-27T19:50:00+07:00`  
*Người phê duyệt:* Người dùng (User Approval)  
*Mã tham chiếu Ground Truth:* `benchmark_v2/RESEARCH_SPEC_v2.md` | `benchmark_v2/ANALYSIS_PLAN.md`

---

## 1. Tuyên Bố Đóng Băng Chính Thức (Official Freeze Statement)

Căn cứ theo Master Plan Benchmark v2 (§8 mục C8 và Gate G3), bộ dữ liệu thử nghiệm toàn diện cho Benchmark v2 đã được:
1. Soạn thảo hoàn tất theo đúng 4 nhóm taxonomy (`DH-A`, `DH-S`, `SUP`, `DS`), 5 kịch bản User Case ($U_1 \dots U_5$), và 4 sub-track kỹ thuật (`SER`, `CDR`, `WTR`, `PMR`).
2. Kiểm tra xác thực 7 lớp bởi `validate_dataset.py` đạt **100% PASS** (0 lỗi cú pháp, 0 rò rỉ canary, 0 placeholder, ánh xạ tool chính xác).
3. Người dùng rà soát và chính thức phê duyệt tại Cổng duyệt G3.

> [!IMPORTANT]
> **QUY TẮC ĐÓNG BĂNG BẤT KHẢ XÂM PHẠM:**
> Toàn bộ các file dữ liệu được liệt kê dưới đây chính thức được **ĐÓNG BĂNG (FROZEN)**. Nghiêm cấm mọi hành vi chỉnh sửa, thêm, bớt hoặc thay đổi nội dung testcase/nhãn/ngữ cảnh trước các đợt chạy thực nghiệm chính thức.

---

## 2. Bảng Băm Tính Toàn Vẹn Dữ Liệu (SHA-256 Manifest)

| Tệp Dữ Liệu | Đường Dẫn Tương Đối | SHA-256 Checksum | Mô Tả |
|---|---|---|---|
| `env_spec.json` | `benchmark_v2/data/env_spec.json` | `373ebc804d7dcef1027c67d1b69d85fcd18322c09a1b3f4a2a1654de80c45abd` | Đặc tả môi trường 5 phòng ($U_1 \dots U_5$) và 7 canary tokens |
| `triage_v1.csv` | `benchmark_v2/data/triage_v1.csv` | `d2275b00e23ff6fe68c509462d4a3e27fcb4108566fff1f50b1624539778bbe0` | Bảng phân loại 60 testcases từ v1 |
| `attackers.json` | `benchmark_v2/data/attackers.json` | `89776b0e8edc070ae2f11f1eb9f0873046a17dd27b4ba6e66e5b4d13368a1d8f` | 60 attacker chuẩn hóa (15 DH-A, 10 DH-S, 15 SUP, 20 DS) |
| `user_cases.json` | `benchmark_v2/data/user_cases.json` | `f36ac4bd420e03acac01bb6914622f4c09fb2406692d92e5af6a44c8a31d0bad` | 5 User Cases và 15 neutral descriptions sạch |
| `trackA_testcases.json` | `benchmark_v2/data/generated/trackA_testcases.json` | `48f94b8c77cd56816c080b9dfed18699e72a2265eeb6b53b46c11c9acaaa614d` | 315 testcases Track A (262 attack hợp lệ, 38 lọc, 15 BU) |
| `synthesis_report.md` | `benchmark_v2/data/generated/synthesis_report.md` | `db3f7458343dc8938edb4eb670c7bca49feec4d9a4b5cdb653b0c229e2e4d0c7` | Báo cáo chi tiết ma trận Descartes và lý do lọc 38 ca |
| `trackB_testcases.json` | `benchmark_v2/data/trackB_testcases.json` | `f6745b44b5e2c7f311e36800a10eda5ab75834634474bb16655a1b09a3770f97` | 16 testcases Track B đã tách nhãn độc lập |
| `ANALYSIS_PLAN.md` | `benchmark_v2/ANALYSIS_PLAN.md` | `505cd8af0d9a21c4ba0a56af3329a1f6ab186633337049a0d27b06eb170cbb0c` | Kế hoạch phân tích thực nghiệm và công thức Wilson 95% CI |

---

## 3. Tổng Kết Số Lượng Testcases

| Phân Vùng | Tổng Ca | Số Ca Hợp Lệ Metric Chính | Số Ca Đối Chứng ($BU$) | Số Ca Giữ Lại Đối Chiếu ($ASR_{all}$) |
|---|:---:|:---:|:---:|:---:|
| **Track A (Indirect Prompt Injection)** | **315** | 262 ($ASR_{\text{valid}}$) | 15 ($BU$) | 38 (lọc do trùng hành vi bảo vệ) |
| **Track B (System Robustness & Manipulation)** | **16** | 16 (SER: 4, CDR: 4, WTR: 4, PMR: 4) | — | — |
| **TOÀN BỘ BENCHMARK V2** | **331** | **278** | **15** | **38** |

---

## 4. Chuyển Giao Sang Phase D

Bộ dữ liệu v2 đã hoàn tất đóng băng và sẵn sàng cung cấp nguồn đầu vào cố định cho:
- **D1 (Runner v2):** `benchmark_v2/runner/run_benchmark.py` (chạy qua REST/direct, ghi trajectory, timeout, resume).
- **D2 (Evaluator v2):** `benchmark_v2/evaluator/evaluate_v2.py` (trajectory matching xác định, Wilson 95% CI, xuất `summary.json` & `report.md`).
- **D3 (Sanity Agents):** Kiểm tra evaluator với 4 agent giả định (`Obedient`, `Deaf`, `Paranoid`, `Broken`).
