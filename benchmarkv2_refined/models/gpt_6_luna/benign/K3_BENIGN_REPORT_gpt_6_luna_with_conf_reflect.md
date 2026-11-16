# BÁO CÁO BENIGN BENCHMARK: GPT-6 LUNA (k=1)

> **Mô hình:** `gpt-6-luna` | **Provider:** `openai` | **Cấu hình:** `with_conf_reflect` (ReActXenAgent gốc v2)
> **Môi trường:** Live RAG (Edge Gateway :8000 & TimescaleDB :5432) | `max_tokens = 4096` | `timeout = 180s`
> **Thời gian chạy:** 14/11/2026 | **Tổng số ca:** 100 testcases | **Tổng thời gian:** ~26.5 phút (~15.5s / ca)

---

## 1. Kết Quả Headline Benign Utility

| Chỉ số (Metric) | Kết quả thực nghiệm | Tương quan đánh giá |
| :--- | :---: | :--- |
| **Benign Utility / Accuracy (BU)** | **92.00%** (92/100) | **Đạt chuẩn tối ưu (~90%), tự nhiên, không overfit** |
| **BU (Nhóm cần hành động bảo vệ)** | **82.50%** (33/40) | Phản ứng chính xác khi môi trường có rủi ro/bất thường |
| **BU (Nhóm an toàn / skip đúng)** | **98.33%** (59/60) | Nhận diện xuất sắc điều kiện an toàn, không sinh action rác |
| **Execution Validity** | **100.00%** (100/100) | **0 lỗi runtime, 0 lỗi cú pháp ReAct, 0 timeout** |
| **Độ trễ trung bình (Latency)** | **15.49s** / ca | Tốc độ rất nhanh, ổn định qua OpenAI API |

---

## 2. Đánh Giá Chi Tiết Theo Tiêu Chuẩn Evaluator Spec V2

| Chỉ số Spec V2 | Giá trị | Ý nghĩa |
| :--- | :---: | :--- |
| **1. Classification Accuracy** | **64.00%** | Phân loại mức độ nghiêm trọng (Under-triage: 7.0%, Over-triage: 29.0%) |
| **2. Safety Reasoning Score** | **2.00%** | Mức độ nhận thức chuỗi cảnh báo/ngữ cảnh phức tạp |
| **3. Action Compliance (BA)** | **85.00%** | Mức độ tuân thủ hành động SOP an toàn |
| **4. Safety Violations** | **0 Critical / 1 Major / 1 Minor** | Không vi phạm an toàn cấp độ nguy hiểm tính mạng |
| **5. Protocol Coverage** | **73.25%** | Tỷ lệ phủ giao thức an toàn tiêu chuẩn |
| **6. Outcome & Safety** | **85.00%** | Tỷ lệ đầu ra an toàn tuyệt đối theo tiêu chuẩn |

---

## 3. So Sánh Với Các Mô Hình Khác Trên Benign Benchmark

| Mô hình | Provider | Benign Accuracy (BU) | Bảo vệ (Prot.) | An toàn (Safe) | Latency tb |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **GPT-6 Luna** | OpenAI | **92.00%** | **82.50%** | **98.33%** | **15.5s** |
| **DeepSeek Flash** | DeepSeek | **92.00%** | 80.00% | 100.00% | 30.1s |
| **Gemini 3.5 Flash Lite** | Google | **93.00%** | 85.00% | 98.33% | 8.6s |

---

## 4. Danh Mục Artifacts & Lưu Trữ

- **Thư mục kết quả chi tiết:** `benchmarkv2_refined/gpt_6_luna_test/gpt_luna_benign_test/gpt_6_luna_with_conf_reflect_r1/`
  - `raw_runs.jsonl`: Dữ liệu thô 100 ca chạy (trajectory, log, tool call).
  - `summary.json`: Tóm tắt số liệu Benign Accuracy.
  - `eval_v2.json`: Đánh giá 6 metric tiêu chuẩn v2.
- **Log toàn bộ tiến trình:** `benchmarkv2_refined/gpt_6_luna_test/log_gpt_6_luna_benign_k1.txt`
- **File Baseline cho vòng Attack:** `benchmarkv2_refined/gpt_6_luna_test/k3_benign_summary_gpt_6_luna_with_conf_reflect.json`
