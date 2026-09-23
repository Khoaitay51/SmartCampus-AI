# SmartCampus AI Agent — Scenario Resolution & Functional Requirements Guide

Tài liệu hướng dẫn chi tiết quy trình xử lý các kịch bản sự kiện (Scenarios) của AI Agent dựa trên yêu cầu chức năng (Functional Requirements) trong hệ thống SmartCampus.

---

## 1. Tổng quan Kiến trúc Suy luận (ReAct Engine)

AI Agent vận hành dựa trên kiến trúc **ReAct (Reasoning + Acting)** tích hợp cơ chế **Review & Reflect** theo vòng lặp tự phản hồi:

```
                  ┌──────────────────────────────┐
                  │   Event Payload & Context    │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │ ReAct Loop (Step 1..N)│
                     │  - Think (Thought)    │
                     │  - Observe (RAG Tool) │
                     │  - Act (Finish / Tool)│
                     └───────────┬───────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │ Review Agent          │
                     │ (Accomplished / Retry)│
                     └───────────┬───────────┘
                                 │
                   ┌─────────────┴─────────────┐
                   ▼                           ▼
            [Accomplished]             [Not Accomplished]
                   │                           │
                   ▼                           ▼
        ┌──────────────────────┐   ┌──────────────────────┐
        │ Final Safety Check   │   │ Reflect Agent        │
        │ (Mode Permission &   │   │ (Rút kinh nghiệm &   │
        │  Confidence Threshold│   │  vòng lặp mới)       │
        │  Check)              │   └──────────────────────┘
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │    AgentResponse     │
        └──────────────────────┘
```

---

## 2. Chi tiết 5 Kịch bản Xử lý theo Requirements

### 🔴 Kịch bản 1: `smoke_detected` (Phát hiện khói / Nguy cơ hỏa hoạn)

* **Yêu cầu chức năng**: Đảm bảo an toàn tính mạng & tài sản tối đa, phản ứng tức thì khi có nguy cơ cháy nổ.
* **Điều kiện kích hoạt**: Cảm biến MQ2 vượt ngưỡng (`smoke_state == "suspected"` hoặc `smoke_value > 400`).
* **Quy trình xử lý của Agent**:
  1. **Tra cứu dữ liệu (Observe)**:
     - Gọi RAG Tool `get_telemetry(metric="smoke", window="15m")` và `get_telemetry(metric="temperature", window="15m")`.
     - Kiểm tra số lượng người hiện có trong phòng qua `operational_context.occupancy.current_count`.
  2. **Đánh giá & Suy luận (Think)**:
     - Nếu chỉ số khói tăng liên tục và nhiệt độ có dấu hiệu tăng ➔ Xác định nguy cơ cháy thật.
     - Đặt mức độ khẩn cấp `urgency = "high"`, độ tin cậy `confidence >= 0.95`.
  3. **Khuyến nghị thực thi (Act)**:
     - **Recommendation chính**: `trigger_buzzer` với `pattern: "emergency"`.
     - **Recommendation thay thế / mở rộng**: `set_mode` ➔ `"EMERGENCY"`, `set_door` ➔ `"unlocked"`, `send_alert` ➔ thông báo khẩn cấp tới ban quản lý.

---

### 🟡 Kịch bản 2: `temperature_anomaly` (Bất thường nhiệt độ / Nắng nóng / Quá nhiệt)

* **Yêu cầu chức năng**: Cải thiện chất lượng môi trường phòng học, cân bằng giữa sự thoải mái và tiết kiệm năng lượng.
* **Điều kiện kích hoạt**: Nhiệt độ đo được `> 32.0°C` hoặc CO2 `> 1000 ppm` trong thời gian vận hành.
* **Quy trình xử lý của Agent**:
  1. **Tra cứu dữ liệu (Observe)**:
     - Gọi RAG Tool `get_telemetry(metric="temperature", window="15m")` và `get_telemetry(metric="co2", window="15m")`.
     - Tra cứu lịch học qua RAG Tool `get_schedule()` hoặc thông tin `active_session`.
  2. **Đánh giá & Suy luận (Think)**:
     - Nếu phòng đang có lớp học (`LECTURE` / `SELF_STUDY`) và có sinh viên ➔ Cần làm mát khẩn cấp.
     - Kiểm tra ma trận quyền hạn: Trong chế độ thi (`EXAM`), **KHÔNG** được tự ý mở cửa (`set_door`) hoặc bật còi (`trigger_buzzer`), chỉ được bật quạt (`set_fan`).
  3. **Khuyến nghị thực thi (Act)**:
     - **Recommendation**: `set_fan` ➔ `state: "on"`.
     - **Alternative**: `send_alert` ➔ Gửi nhắc nhở mở cửa sổ / kiểm tra hệ thống điều hòa.

---

### 🟢 Kịch bản 3: `occupancy_change` (Thay đổi mật độ phòng / Năng lượng)

* **Yêu cầu chức năng**: Tự động hóa tối ưu điện năng tiêu thụ, tắt thiết bị khi không sử dụng.
* **Điều kiện kích hoạt**: Phòng trống (`current_count == 0`) sau khi buổi học kết thúc hoặc số lượng người ra/vào thay đổi đột biến.
* **Quy trình xử lý của Agent**:
  1. **Tra cứu dữ liệu (Observe)**:
     - Gọi RAG Tool `get_room_history(hours=2)` kiểm tra lịch sử FSM.
     - Tra cứu `get_attendance()` để xác nhận buổi học đã kết thúc.
  2. **Đánh giá & Suy luận (Think)**:
     - Nếu phòng đã hết giờ học và không còn ai trong phòng quá 15 phút ➔ Cần chuyển sang chế độ tiết kiệm điện.
  3. **Khuyến nghị thực thi (Act)**:
     - **Recommendation**: `set_fan` ➔ `state: "off"`.
     - **Alternative**: `set_mode` ➔ `"SAVING"`.

---

### 🔵 Kịch bản 4: `rfid_unknown` (Thẻ RFID chưa đăng ký / Cảnh báo an ninh)

* **Yêu cầu chức năng**: Kiểm soát ra vào, phát hiện xâm nhập trái phép vào khu vực hạn chế.
* **Điều kiện kích hoạt**: Phát hiện quẹt thẻ không có trong danh sách đăng ký (`card_uid` lạ).
* **Quy trình xử lý của Agent**:
  1. **Tra cứu dữ liệu (Observe)**:
     - Gọi RAG Tool `get_attendance(session_id=...)` xác minh danh sách lớp.
     - Tra cứu `get_schedule()` kiểm tra phòng có đang trong giờ thi (`EXAM`) hoặc bị khóa (`LOCK`).
  2. **Đánh giá & Suy luận (Think)**:
     - Nếu phòng đang ở chế độ `LOCK` hoặc `EXAM` ➔ Cảnh báo vi phạm an ninh.
  3. **Khuyến nghị thực thi (Act)**:
     - **Recommendation**: `send_alert` ➔ Thông báo tới bảo vệ / giảng viên trực ban với `level: "warning"`.
     - **Alternative**: `trigger_buzzer` ➔ `pattern: "short"` (Còi bíp cảnh báo tại chỗ).

---

### ⚪ Kịch bản 5: `manual_trigger` (Kích hoạt đánh giá thủ công từ Dashboard UI)

* **Yêu cầu chức năng**: Phục vụ tính năng "Evaluate Room" trên giao diện quản trị / Digital Twin.
* **Điều kiện kích hoạt**: Bấm nút Yêu cầu đánh giá trên UI.
* **Quy trình xử lý của Agent**:
  1. **Tra cứu dữ liệu (Observe)**:
     - Gọi RAG Tool `search_history()` và `compare_rooms()` để lấy bức tranh tổng thể sức khỏe phòng học so với các phòng khác.
  2. **Đánh giá & Suy luận (Think)**:
     - Tổng hợp toàn bộ chỉ số telemetry, occupancy, lịch học và FSM state hiện tại.
  3. **Khuyến nghị thực thi (Act)**:
     - Trả về báo cáo `analysis` chi tiết kèm các đề xuất tối ưu (nếu có) hoặc trả về `skip: true` kèm lý do `"all_metrics_normal"`.

---

## 3. Ma trận Quyền hạn Tool theo Chế độ Phòng (Room Mode Permissions)

Để đảm bảo an toàn tuyệt đối, kết quả đề xuất của Agent luôn phải trải qua hàm kiểm tra `is_tool_allowed_in_mode`:

| Tool Action | SAVING | SELF_STUDY | LECTURE | EXAM | LOCK | SUSPECTED | EMERGENCY |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `set_fan` |  Yes |  Yes |  Yes |  Yes |  No |  Yes |  Yes |
| `set_door` |  Yes |  Yes |  Yes | ❌ **No** | ❌ **No** |  Yes |  Yes |
| `set_mode` |  Yes |  Yes |  Yes |  Yes |  Yes |  Yes |  Yes |
| `trigger_buzzer` |  Yes |  Yes |  Yes | ❌ **No** |  Yes |  Yes |  Yes |
| `send_alert` |  Yes |  Yes |  Yes |  Yes |  Yes |  Yes |  Yes |
| `set_led` |  Yes |  Yes |  Yes |  Yes |  No |  No |  No |

> ⚠️ **Chú ý**: Trong chế độ thi **`EXAM`**, Agent bị **CẤM** tự ý mở cửa (`set_door`) hoặc bấm còi báo (`trigger_buzzer`) để tránh gây gián đoạn buổi thi.

---

## 4. Hướng dẫn Chạy Thử nghiệm & Test Tự động

### Chạy Demo mô phỏng các Kịch bản
Sử dụng script `run_agent_demo.py` để xem luồng ReAct suy luận trực quan:
```powershell
cd d:\project_dads\SmartCampus-main\SmartCampus\AI
python run_agent_demo.py
```

### Chạy bộ Unit Tests đầy đủ
Chạy bộ kiểm thử tự động kiểm tra 7 test cases cốt lõi:
```powershell
python -m unittest discover -s tests
```

---

## 5. Cấu trúc Output & Audit Trail

Mỗi lần thực thi `/evaluate`, kết quả sẽ được tự động lưu dưới dạng JSON audit trail tại thư mục `AI/output/`:
```json
{
  "event_id": "uuid",
  "recommendation": {
    "tool_name": "set_fan",
    "tool_params": {"room_id": "uuid", "state": "on"},
    "reason": "Nhiệt độ phòng tăng vọt lên 35.5°C trong giờ học LECTURE.",
    "confidence": 0.92,
    "urgency": "high"
  },
  "alternatives": [...],
  "analysis": "Nhiệt độ phòng học A101 đo được 35.5°C vượt ngưỡng an toàn...",
  "skip": false,
  "skip_reason": null,
  "tool_calls_log": [...],
  "structured_trace": [...]
}
```
