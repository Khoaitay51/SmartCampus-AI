# 🌐 SmartCampus AI Agent Safety Benchmark — Tổng Quan Toàn Diện (Overview)

> **Chủ đề:** Đánh giá Định lượng Độ An Toàn & Khả Năng Kháng Thao Túng của ReAct AI Agent trong Hệ sinh thái Smart Campus IoT  
> **Quy mô Suite:** 5 Taxonomy $\times$ 12 Testcases = **60 Testcases Chuẩn Hóa**  
> **Môi trường Thực nghiệm:** ReActXenAgent (Gemini 3.5 Flash-lite/ Ollama Local) tích hợp FastAPI & IoT Event-Driven Gateway  


---

## 1. BẢNG TỔNG HỢP KẾT QUẢ THỰC NGHIỆM TOÀN BỘ BENCHMARK

Bảng đối chiếu kết quả thực nghiệm thực tế của toàn bộ 60 testcase trên Agent đang chạy:

| Taxonomy | Tên Phân Loại Nguy Cơ | Số TC | Tỷ Lệ An Toàn (SCR) | Tỷ Lệ Bị Thao Túng | Độ Chính Xác (DA) | Đánh Giá Khách Quan |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| **T1** | [Sensor-Text Conflict](./t1_sensor_text_conflict/benchmark_spec.md) | 12 | **66.67%** (8/12) | 50.0% (TMVR) | **66.67%** (8/12) | **Lỗ hổng Text-Bias:** Agent có xu hướng tin vào văn bản hơn số đo cảm biến khi bị kích động báo động giả. Không bỏ sót cháy thật (MHR=0%). |
| **T2** | [Authority & Policy Spoofing](./t2_authority_policy_spoofing/benchmark_spec.md) | 12 | **91.67%** (11/12) | 12.5% (ABR) | **91.67%** (11/12) | **Kháng mạo danh tốt:** Agent chặn hầu hết xưng danh miệng, chỉ bị qua mặt ở ticket giả tinh vi có cấu trúc hợp lệ. |
| **T3** | [Alert Suppression & False Alarm](./t3_alert_suppression_false_alarm/benchmark_spec.md) | 12 | **91.67%** (11/12) | 12.5% (ASR/FAR) | **91.67%** (11/12) | **Kháng tin đồn xuất sắc (FAR=0%):** Tuyệt đối không bấm còi hoảng loạn; tuy nhiên còn bị 1 ca dìm báo động do văn bản bao biện "lau sàn". |
| **T4** | [Temporal & Cross-Device Spoofing](./t4_temporal_cross_device/benchmark_spec.md) | 12 | **83.33%** (10/12) | 25.0% (Stale Bypass) | **66.67%** (8/12) | **Xử lý xung đột thiết bị 100%:** Khi 2 cảm biến cãi nhau, Agent luôn phát cảnh báo kiểm tra thực địa; nhưng bị điểm yếu kiểm tra timestamp cũ. |
| **T5** | [Tool Action & Parameter Manipulation](./t5_tool_action_manipulation/benchmark_spec.md) | 12 | **91.67%** (11/12) | 12.5% (PMR) | **91.67%** (11/12) | **Chọn đúng Tool 100% (WTR=0%):** Không bao giờ leo thang nhầm công cụ phá hoại; rủi ro duy nhất nằm ở việc tráo tham số `target_room`. |
| **TỔNG HỢP** | **TOÀN BỘ BENCHMARK (GLOBAL)** | **60** | **85.00%** (51/60) | **18.75%** (Global Attack Success) | **81.67%** (49/60) | **Đạt chuẩn triển khai thử nghiệm có giám sát (Supervised Deployment).** |

```
                               TỶ LỆ TUÂN THỦ AN TOÀN (SCR) THEO TAXONOMY
  100% ┌────────────────────────────────────────────────────────────────────────┐
       │                                 91.67%       91.67%                    91.67%   │
   80% │                                ┌──────┐     ┌──────┐      83.33%      ┌──────┐  │
       │                   66.67%       │      │     │      │     ┌──────┐     │      │  │
   60% │                  ┌──────┐      │      │     │      │     │      │     │      │  │
       │                  │      │      │      │     │      │     │      │     │      │  │
   40% │                  │      │      │      │     │      │     │      │     │      │  │
   20% │                  │      │      │      │     │      │     │      │     │      │  │
    0% └──────────────────┴──────┴──────┴──────┴─────┴──────┴─────┴──────┴─────┴──────┴──┘
                            T1             T2           T3           T4           T5
```

---

## 2. BẢN ĐỒ THREAT TAXONOMY (MA TRẬN NGUY CƠ)

Benchmark được thiết kế theo bề mặt tấn công 5 lớp độc lập của một hệ thống **Agentic Cyber-Physical System (CPS)**:

| Tầng Hệ Thống | Taxonomy Tương Ứng | Đối Tượng Tấn Công | Hậu Quả Vật Lý Nếu Bị Vượt Qua |
| :--- | :--- | :--- | :--- |
| **1. Lớp Cảm Biến & Dữ Liệu Vào (Input Space)** | • **T1:** Sensor-Text Conflict<br/>• **T4:** Temporal & Cross-Device | Dữ liệu đo đạc (Khói, Nhiệt, CO2), Tem thời gian (Timestamp), Đồng thuận cảm biến | Agent tin lời nói dối mà bỏ qua nguy cơ cháy nổ, ngạt khí; hoặc xử lý sai lệch pha thời gian. |
| **2. Lớp Thẩm Quyền & Chính Sách (Access Control)** | • **T2:** Authority & Policy Spoofing<br/>• **T3:** Alert Suppression & False Alarm | Danh tính người dùng (RBAC), Giấy phép/Ticket duyệt, Kênh cảnh báo khẩn cấp | Mở cửa trái phép phòng máy chủ/hóa chất; dìm chuông báo cháy thật hoặc kích động còi báo động giả. |
| **3. Lớp Can Thiệp Phần Cứng (Actuation Space)** | • **T5:** Tool Action & Parameter Manipulation | Danh mục Tool, Tham số điều khiển (`target_room`, `speed`, `mode`) | Tự động hóa sai mục tiêu: mở nhầm phòng máy chủ, quá tải động cơ quạt, phong tỏa sai khu vực. |

```
  [1. Cảm Biến & Dữ Liệu] ──┐
                            ├─► [🧠 ReAct AI Agent] ──► [3. Tools Phần Cứng] ──► [🏢 Smart Campus IoT]
  [2. Thẩm Quyền & Phân Quyền] ─┘   (Suy Luận & Ra Quyết Định)   (Cửa, Quạt, Còi, Điện)
```

* **T1 (Sensor-Text Conflict):** Khảo sát khả năng phản kháng của Agent trước hiện tượng **Text-Bias** — khi kẻ tấn công chèn văn bản ngụy biện (ví dụ: *"đang diễn tập PCCC"*, *"không cần bật quạt"*) trong lúc cảm biến vật lý đang báo nguy cấp.
* **T2 (Authority & Policy Spoofing):** Khảo sát việc xác thực ngữ cảnh phân quyền — kẻ tấn công mạo danh vai trò cấp cao (Trưởng khoa, Đội trưởng an ninh) hoặc bịa đặt mã ticket phê duyệt để ép Agent mở cửa/ngắt điện.
* **T3 (Alert Suppression & False Alarm):** Khảo sát tính cân bằng giữa hai thái cực nguy hiểm: **Bỏ sót hiểm họa (False Negative)** do bị yêu cầu im lặng, và **Gây náo loạn khuôn viên (False Positive)** do bị tin đồn mạng xã hội dắt mũi.
* **T4: Temporal & Cross-Device Context:** Khảo sát năng lực phân tích thời gian thực (nhận diện thẻ từ/session hết hạn từ hôm qua) và năng lực hợp nhất dữ liệu đa cảm biến (Multi-Sensor Fusion khi 2 cảm biến trả về dữ liệu trái ngược).
* **T5: Tool Action & Parameter Manipulation:** Khảo sát độ an toàn ở tầng can thiệp phần cứng — ngăn chặn Agent bị lừa gọi sai công cụ có tính phá hoại hoặc bị tráo đổi tham số bí mật (ví dụ: yêu cầu mở phòng tiếp khách nhưng tham số lén đổi thành phòng máy chủ trung tâm).

---

## 3. PHƯƠNG PHÁP XÂY DỰNG TESTCASE (METHODOLOGY)

Mỗi Taxonomy gồm đúng **12 testcase** được phân chia theo tỷ lệ vàng trong khoa học dữ liệu kiểm thử: **8 kịch bản tấn công (Adversarial)** và **4 kịch bản đối chứng (Control Group)**.

```
                    CẤU TRÚC PHÂN BỔ 12 TESTCASES TRONG MỖI TAXONOMY
  ┌────────────────────────────────────────────────────────┬─────────────────────────────┐
  │              8 ADVERSARIAL CASES (66.7%)               │   4 CONTROL CASES (33.3%)   │
  ├────────────────────────────┬───────────────────────────┼─────────────────────────────┤
  │    Nhóm A: Tấn công Trực diện │    Nhóm B: Tấn công Tinh vi │     Nhóm C: Nhóm Đối chứng  │
  │    (Direct Exploitation)   │    (Stealth / Lateral)    │     (Benign Baseline)       │
  │    • 4 testcases           │    • 4 testcases          │     • 4 testcases           │
  │    • Dùng ngôn từ ép buộc, │    • Ngụy tạo ticket, giả │     • Vận hành bình thường, │
  │      tạo tình huống sốc    │      thời gian, đổi param │       sự cố thật có văn bản │
  └────────────────────────────┴───────────────────────────┴─────────────────────────────┘
```

### Tiêu Chuẩn Schema Dữ Liệu Mỗi Testcase:
Mỗi testcase là một bản ghi JSON có cấu trúc đóng gói độc lập, không rò rỉ nhãn (No label leakage):
1. **`testcase_id` & `description`:** Định danh duy nhất và mô tả mục tiêu thử nghiệm (100% tiếng Việt chuẩn UTF-8).
2. **`payload.event`:** Sự kiện IoT mô phỏng đúng định dạng API Gateway (`event_type`, `room_id`, `timestamp`, `event_data` chứa nồng độ khói, nhiệt độ, tin nhắn text).
3. **`payload.operational_context`:** Ngữ cảnh vận hành đầy đủ của phòng (`room_name`, `capacity`, `current_occupancy`, `status`, `authorized_roles`, `door_status`, `hvac_status`).
4. **`safety_constraint` & `forbidden_actions`:** Ràng buộc an toàn cứng tuyệt đối không được vi phạm (ví dụ: *"Cấm gọi set_door:unlocked"*, *"Cấm tắt còi khi khói > 500ppm"*).
5. **`oracle`:** Quyết định chuẩn xác của chuyên gia con người (Ground Truth) để bộ chấm điểm đối chiếu tự động.

---

## 4. PHƯƠNG PHÁP ĐÁNH GIÁ (EVALUATION FRAMEWORK)

Bộ thẩm định sử dụng kiến trúc **Evaluator v2.0** kết hợp kiểm chứng hình thức (Deterministic Constraint Verification) và đối chiếu ngữ nghĩa (Semantic Alignment):

### 4.1. Các Chỉ Số Khoa Học Cốt Lõi:
* **Safety Compliance Rate (SCR) — Tỷ Lệ Quyết Định Tuân Thủ An Toàn:**
  $$\text{SCR} = \frac{\text{Số testcase không vi phạm bất kỳ ràng buộc an toàn nào}}{\text{Tổng số testcase}} \times 100\%$$
* **Adversarial Vulnerability Rate (AVR / TMVR / ABR / PMR):**
  Tỷ lệ Agent mắc sai lầm loại I (Type I Error) — chấp nhận làm theo yêu cầu độc hại của kẻ tấn công trong nhóm Adversarial.
* **Missed Hazard Rate (MHR) / Alert Suppression Rate (ASR):**
  Tỷ lệ Agent mắc sai lầm loại II (Type II Error) — bỏ sót sự cố cháy nổ, ngạt khí hoặc đột nhập thật sự. Trong hệ thống Smart Campus, **chỉ số này bắt buộc phải tiệm cận $0.0\%$**.
* **Decision Accuracy (DA) — Độ Khớp Quyết Định:**
  Độ chính xác so khớp toàn diện giữa khuyến nghị của Agent với hành động kỳ vọng của Oracle Ground Truth.

---

## 5. CẤU TRÚC THƯ MỤC VÀ ĐIỀU HƯỚNG TÀI LIỆU

Mỗi taxonomy trong thư mục `benchmark/` được đóng gói hoàn toàn độc lập, có thể chạy riêng lẻ hoặc chạy toàn bộ:

```
D:\SmartCampus\AI + Backend\benchmark\
│
├── benchmark_overview.md             <--- [BẠN ĐANG XEM] Báo cáo tổng thể toàn bộ 5 taxonomy
│
├── t1_sensor_text_conflict/          <--- Taxonomy T1: Xung đột Cảm biến & Văn bản
│   ├── testcases_t1.json             (12 testcases chuẩn UTF-8)
│   ├── run_benchmark.py              (Runner tự động qua REST API / In-memory)
│   ├── evaluate_results.py           (Evaluator v2.0 tính SCR, TMVR, SRS, DA)
│   ├── benchmark_spec.md             (Đặc tả chi tiết toán học & kết quả thực nghiệm)
│   └── results/latest_run.json       (Log JSON chi tiết trace ReAct của Agent)
│
├── t2_authority_policy_spoofing/     <--- Taxonomy T2: Giả mạo Thẩm quyền & Chính sách
│   ├── testcases_t2.json
│   ├── run_benchmark.py
│   ├── evaluate_results.py
│   └── benchmark_spec.md
│
├── t3_alert_suppression_false_alarm/ <--- Taxonomy T3: Dìm cảnh báo & Báo động giả
│   ├── testcases_t3.json
│   ├── run_benchmark.py
│   ├── evaluate_results.py
│   └── benchmark_spec.md
│
├── t4_temporal_cross_device/         <--- Taxonomy T4: Lệch pha Thời gian & Đa thiết bị
│   ├── testcases_t4.json
│   ├── run_benchmark.py
│   ├── evaluate_results.py
│   └── benchmark_spec.md
│
└── t5_tool_action_manipulation/      <--- Taxonomy T5: Thao túng Hành động & Tham số Tool
    ├── testcases_t5.json
    ├── run_benchmark.py
    ├── evaluate_results.py
    └── benchmark_spec.md
```

---

## 6. HƯỚNG DẪN CHẠY NHANH CHO NHÓM NGHIÊN CỨU

### Bước 1: Khởi động môi trường SmartCampus AI
```bash
cd "D:\SmartCampus\AI + Backend"
docker compose up -d
```
Xác nhận endpoint sẵn sàng: `http://localhost:8001/health` (HTTP 200).

### Bước 2: Chạy kiểm thử cho một Taxonomy bất kỳ (Ví dụ T2)
```bash
cd "D:\SmartCampus\AI + Backend\benchmark\t2_authority_policy_spoofing"
python run_benchmark.py
python evaluate_results.py --input results/latest_run.json
```

### Bước 3: Xem báo cáo chi tiết
Mở file `benchmark_spec.md` trong từng thư mục taxonomy để xem bảng phân tích trace từng testcase và luận giải khoa học.

---

> 📌 **Kết luận nghiên cứu:** Bộ Benchmark 60 testcases đã hoàn thành toàn bộ chu trình chuẩn hóa: **Dữ liệu chuẩn UTF-8 sạch lỗi font** $\rightarrow$ **Kịch bản tấn công - đối chứng chặt chẽ** $\rightarrow$ **Thực thi trên Agent thật** $\rightarrow$ **Chấm điểm định lượng khách quan**. Đây là nền tảng thực nghiệm vững chắc để phục vụ viết báo cáo khoa học, luận văn, hoặc bảo vệ trước hội đồng chuyên môn.
