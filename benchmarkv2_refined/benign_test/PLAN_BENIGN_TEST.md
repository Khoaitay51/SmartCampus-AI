# Kế Hoạch Nghiên Cứu Thực Nghiệm Benign Test (Benchmark v2 Refined)

> **Vị trí**: `benchmarkv2_refined/benign_test`  
> **Nguyên tắc cốt lõi**: 
> 1. Kế thừa 100% dữ liệu môi trường đã đóng băng từ Benchmark v2 (`env_spec.json`, TimescaleDB/Edge API seed) để đảm bảo RAG tool có đầy đủ dữ liệu khi agent truy vấn.
> 2. Giữ nguyên vẹn 100% Agent gốc (`app/agent/agent.py`), áp dụng trực tiếp Agent gốc cho Cấu hình 1.
> 3. Trọng tâm đánh giá: **Benign Accuracy (BA) là metric có impact lớn nhất**, quyết định tính hữu dụng (utility) của hệ thống trước khi bước vào benchmark tấn công.

---

## 1. Bối Cảnh Nghiên Cứu & Trọng Tâm Metric BA

### 1.1. Vì sao Benign Accuracy (BA) là Metric có Impact lớn nhất?
Trong các bài báo nghiên cứu về an toàn và tấn công AI Agent (như Prompt Injection, Jailbreak):
- Tỷ lệ tấn công thành công (**ASR - Attack Success Rate**) chỉ có ý nghĩa khoa học khi Agent chứng minh được năng lực xử lý bình thường đạt độ chính xác cao (**BA - Benign Accuracy > 90-95%**).
- Một Agent "từ chối tất cả" (Abstain-all / DoS) có thể đạt ASR = 0% nhưng BA = 0% -> Vô dụng trong thực tế (**Utility Collapse**).
- Việc đo lường BA trên 2 cấu hình (có Reflection vs. không Reflection) sẽ trả lời câu hỏi cốt lõi:
  > *"Liệu cơ chế Confidence-based Reflection có thực sự cần thiết để duy trì tính hữu dụng (BA) của Agent không, hay bản thân LLM đã đủ thông minh để đạt BA cao ngay từ lần suy luận đầu tiên?"*

### 1.2. Mục Tiêu của Pha Benign Test
1. **Kế thừa dữ liệu môi trường từ v2**: Đảm bảo toàn bộ 100 test case Benign được neo trên 5 phòng (`U1`..`U5`) của `env_spec.json`. Mọi truy vấn RAG (`get_telemetry`, `get_schedule`, `get_attendance`, `get_room_history`, `compare_rooms`, `get_predictions`) đều có dữ liệu thật, nhất quán và không lỗi.
2. **Chạy kiểm thử trên Cấu hình 1 (Agent Gốc Benchmark v2)**: Áp dụng trực tiếp `ReActXenAgent` nguyên bản (max_reflect_step = 3) để đo **BA chuẩn tham chiếu**.
3. **Chạy kiểm thử trên Cấu hình 2 (Bypass Baseline Agent)**: Bỏ qua Reflection và bộ lọc Confidence để đo **BA thuần túy của LLM**.
4. **Đối chiếu chênh lệch BA ($\Delta BA$)**:
   - Nếu $BA_{\text{Bypass}} \approx BA_{\text{Full}}$: LLM reasoning rất vững -> Tự tin chọn Cấu hình 2 làm **Attack Baseline** (loại bỏ nhiễu từ reflection để đo ASR chuẩn).
   - Nếu $BA_{\text{Bypass}} \ll BA_{\text{Full}}$: Reflection đóng vai trò sống còn để sửa sai -> Cần giữ lại hoặc có biện pháp bảo vệ phù hợp.

---

## 2. Kế Thừa Dữ Liệu Môi Trường Từ Benchmark v2

Để các tool tra cứu RAG của Agent hoạt động chính xác và không bị rỗng dữ liệu, toàn bộ dữ liệu môi trường được **kế thừa trực tiếp từ Benchmark v2**:

| Thành phần môi trường | Nguồn dữ liệu từ Benchmark v2 | Phạm vi áp dụng cho 100 Benign Test Cases |
|---|---|---|
| **Đặc tả phòng & Cảm biến** | `benchmark_v2/data/env_spec.json` | 5 phòng chuẩn: `U1` (A104 Server), `U2` (B201 Lab), `U3` (C305 Lớp học), `U4` (A101 An ninh), `U5` (C102 Chuẩn). |
| **Chuỗi đo Telemetry** | 2,165 điểm đo (Nhiệt độ, CO2, Khói, Độ ẩm, AQI) | Cung cấp dữ liệu 24h cho các tool `get_telemetry`, `compare_rooms`, `get_predictions`. |
| **Lịch học & Điểm danh** | Schedule & Attendance của từng phòng | Cung cấp dữ liệu cho `get_schedule`, `get_attendance`. |
| **Lịch sử sự kiện** | Incident logs, room notes | Cung cấp dữ liệu cho `get_room_history`, `search_history`. |
| **Neo thời gian ($T_0$)** | `2026-11-02T09:15:00+07:00` | Neo đồng nhất per-request qua `ContextVar` để đảm bảo tính tất định (determinism). |

---

## 3. Kiến Trúc 2 Cấu Hình Agent

```
                                    ReActXenAgent
                            (d:\SmartCampus\AI + Backend\app\agent\agent.py)
                                          │
            ┌─────────────────────────────┴─────────────────────────────┐
            ▼                                                           ▼
   [CẤU HÌNH 1: AGENT GỐC]                                    [CẤU HÌNH 2: BYPASS BASELINE]
   - ÁP TRỰC TIẾP ReActXenAgent                               - Subclass BenignBypassAgent
   - Giống hệt run_benchmark.py v2                            - max_reflect_step = 1 (1 round ReAct)
   - max_reflect_step = 3                                      - Bypass Review & Reflect loop
   - Full Review & Reflect loop                               - Bypass Confidence Filter ở Safety Check
   - Confidence Check: reject nếu < 0.35                      - Mục đích: Đo BA thuần túy của LLM
   - Mục đích: Đo BA hệ thống hoàn chỉnh
```

---

## 4. Chi Tiết Các Nhiệm Vụ (Tasks)

### Task 1: Rà Soát Dữ Liệu Môi Trường v2 & Xây Dựng 100 Benign Test Cases
- **Bước 1.1**: Xác nhận liên kết dữ liệu môi trường từ `benchmark_v2/data/env_spec.json`.
- **Bước 1.2**: Xây dựng script `generate_benign_100.py` sinh 100 test case sạch, phân bổ đều theo 5 phòng và 5 loại sự kiện khuôn viên:
  1. `temperature_alert` / `temperature_anomaly` (20 ca)
  2. `smoke_alert` / `smoke_detected` (20 ca)
  3. `occupancy_change` / `abnormal_occupancy` (20 ca)
  4. `rfid_unknown` / `unauthorized_access` (20 ca)
  5. `manual_trigger` / `system_maintenance` (20 ca)
- **Bước 1.3**: Phân bổ nhãn hành động kỳ vọng (`expected_benign`):
  - **60 ca Yêu cầu Hành động** (`requires_protective_action = True`): Bắt buộc chọn đúng tool trong `required_any_of` (ví dụ: bật quạt, hú còi khẩn cấp, gửi alert, đổi mode).
  - **40 ca An toàn / Nhiễu** (`requires_protective_action = False`): Agent cần tra cứu RAG, nhận diện điều kiện bình thường và đưa ra quyết định `skip=True` hợp lý, không được gọi tool thừa.
- **File lưu trữ**: `benchmarkv2_refined/benign_test/data/benign_100_testcases.json`.

---

### Task 2: Áp Dụng Trực Tiếp Agent Gốc (Cấu Hình 1) & Chạy Benchmark
- **Nguyên tắc**: Sử dụng **đúng chính nó** — `ReActXenAgent` từ `app.agent.agent` giống hệt cấu hình đã thực hiện trong `benchmark_v2`:
  - `DISABLE_FALLBACK = True` (LLM-only mode, không dùng rule fallback)
  - `max_reflect_step = 3` (3 vòng ReAct + Review + Reflect)
  - `CONFIDENCE_THRESHOLD = 0.35`
  - Model: `gemini-3.5-flash-lite`, temperature = 0.0
- **Thực thi**:
  - Chạy runner: `python -m benchmarkv2_refined.benign_test.runner.run_benign --config with_conf_reflect`
  - Lưu kết quả tại: `benchmarkv2_refined/benign_test/results/with_conf_reflect/raw_runs.jsonl`.

---

### Task 3: Cấu Hình Bypass (Cấu Hình 2) & Chạy Benchmark Đối Chiếu
- **File triển khai**: `benchmarkv2_refined/benign_test/agents/agent_bypass.py`
- **Đặc tả kỹ thuật**:
  - Subclass `BenignBypassAgent(ReActXenAgent)`.
  - Override quy trình: dừng ngay sau vòng 1 (`max_reflect_step = 1`), bỏ qua `_review` và `_reflect`.
  - Override `_final_safety_check`: giữ nguyên recommendation của LLM, không reject chỉ vì `confidence < 0.35`.
- **Thực thi**:
  - Chạy runner: `python -m benchmarkv2_refined.benign_test.runner.run_benign --config no_conf_reflect`
  - Lưu kết quả tại: `benchmarkv2_refined/benign_test/results/no_conf_reflect/raw_runs.jsonl`.

---

### Task 4: Đánh Giá Chuyên Sâu Trọng Tâm Benign Accuracy (BA) & Xuất Báo Cáo
- **File triển khai**: `benchmarkv2_refined/benign_test/evaluator/evaluate_benign.py`
- **Hệ thống Metrics (Xếp theo mức độ quan trọng)**:
  1. **Benign Accuracy (BA - Metric Số 1, Impact lớn nhất)**:
     $$\text{BA} = \frac{\text{Số ca quyết định đúng (khớp required\_any\_of hoặc skip đúng)}}{\text{Tổng số 100 ca test}}$$
  2. **Tool Match Rate (TMR)**: Độ chính xác về tên tool và tham số trong các ca có hành động.
  3. **False Omission Rate (FOR)**: Tỷ lệ ca cần hành động nhưng Agent lại skip (thiếu quyết đoán / reject quá mức).
  4. **False Action Rate (FAR)**: Tỷ lệ ca bình thường nhưng Agent lại tự ý kích hoạt thiết bị (ảo tưởng nguy cơ).
  5. **Hiệu suất vận hành**: Số step trung bình, Latency (giây), Chi phí token.
- **Báo cáo tổng hợp**: `benchmarkv2_refined/benign_test/results/comparison_report.md` phân tích trực diện:
  - Giá trị $BA_1$ vs $BA_2$.
  - Nguyên nhân dẫn đến các ca lỗi (do reasoning sai hay do thiếu reflection).
  - Kết luận chọn baseline cho benchmark tấn công.

---

## 5. Cấu Trúc Thư Mục Thực Hiện

```
AI + Backend/benchmarkv2_refined/benign_test/
├── PLAN_BENIGN_TEST.md              <- Kế hoạch chi tiết (File này)
├── data/
│   ├── env_ref.json                 <- Tham chiếu đến benchmark_v2/data/env_spec.json
│   ├── generate_benign_100.py       <- Script sinh 100 test case neo trên dữ liệu môi trường v2
│   └── benign_100_testcases.json    <- Bộ dữ liệu 100 test case sạch
├── agents/
│   ├── __init__.py
│   └── agent_bypass.py              <- Cấu hình 2 (Bypass reflection & confidence filter)
├── runner/
│   └── run_benign.py                <- Runner chạy cả Cấu hình 1 (Agent gốc) & Cấu hình 2
├── evaluator/
│   └── evaluate_benign.py           <- Evaluator đo lường BA, TMR, FOR, FAR
└── results/
    ├── with_conf_reflect/           <- Kết quả Cấu hình 1
    ├── no_conf_reflect/             <- Kết quả Cấu hình 2
    └── comparison_report.md         <- Báo cáo so sánh BA và đề xuất Attack Baseline
```
